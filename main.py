
import os
import base64
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr, formataddr
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
import pytesseract
from PIL import Image
import requests
from io import BytesIO
import smtplib
from email.mime.text import MIMEText

# Load environment variables
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
OCR_MODE = os.getenv("OCR_MODE", "off")

# Load model
tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-1_5")
model = AutoModelForCausalLM.from_pretrained("microsoft/phi-1_5", trust_remote_code=True)
generator = pipeline("text-generation", model=model, tokenizer=tokenizer)

def extract_text_from_image(url):
    response = requests.get(url)
    img = Image.open(BytesIO(response.content))
    return pytesseract.image_to_string(img)

def generate_reply(email_body):
    prompt = f"""You are a polite assistant. Write a reply to this email:

{email_body}

Reply:"""
    result = generator(prompt, max_new_tokens=200, do_sample=True)[0]['generated_text']
    return result.replace(prompt, "").strip()

def send_reply_email(to_address, subject, body):
    from_address = GMAIL_USER
    msg = MIMEText(body, "plain", "utf-8")
    msg['Subject'] = f"Re: {subject}"
    msg['From'] = formataddr(("Jarvis Mail Assistant", from_address))
    msg['To'] = to_address

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_PASS)
            server.sendmail(from_address, [to_address], msg.as_string())
        print(f"✅ Reply sent to {to_address}")
    except Exception as e:
        print(f"❌ Failed to send reply: {e}")

def fetch_latest_email():
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")
        _, search_data = mail.search(None, "UNSEEN")
        email_ids = search_data[0].split()
        if not email_ids:
            return None
        _, msg_data = mail.fetch(email_ids[-1], "(RFC822)")
        msg = email.message_from_bytes(msg_data[0][1])
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8")
        from_address = parseaddr(msg["From"])[1]
        body = ""
        image_urls = []
        for part in msg.walk():
            content_type = part.get_content_type()
            if content_type == "text/plain":
                body = part.get_payload(decode=True).decode()
            elif content_type.startswith("image/"):
                filename = part.get_filename()
                data = part.get_payload(decode=True)
                with open(filename, "wb") as f:
                    f.write(data)
                image_urls.append(filename)
        if OCR_MODE == "on" and image_urls:
            for img_path in image_urls:
                body += "\n\n[OCR Text]:\n" + pytesseract.image_to_string(Image.open(img_path))
        return subject, body, from_address
    except Exception as e:
        print(f"Error fetching email: {e}")
        return None

def main():
    latest = fetch_latest_email()
    if latest:
        subject, body, from_address = latest
        print(f"📨 Subject: {subject}")
        print(f"📜 Email Body:\n{body}")
        reply = generate_reply(body)
        print(f"📝 Generated Reply:\n{reply}")
        send_reply_email(from_address, subject, reply)
    else:
        print("📭 No new emails.")

if __name__ == "__main__":
    main()
