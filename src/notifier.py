import smtplib
import logging
import configparser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from datetime import datetime

class EmailNotifier:
    def __init__(self, email_config):
        self.recipient_email = email_config.get('recipient_email')
        self.subject_template = email_config.get('subject_template', 'Found: {item_title} at ${price}')
        self.message_template = email_config.get('message_template', 
                                               'Found a {item_title} selling for ${price} in {location}.\nHere\'s the link: {url}')
        self.smtp_server = email_config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = int(email_config.get('smtp_port', 465))
        
        self._load_credentials()
            
    def _load_credentials(self):
        try:
            config = configparser.ConfigParser()
            if not os.path.exists('password.ini'):
                raise ValueError("password.ini file not found")
                
            config.read('password.ini')
            if 'Email' not in config:
                raise ValueError("password.ini missing [Email] section")
                
            self.sender_email = config['Email'].get('sender_email')
            self.sender_password = config['Email'].get('sender_password')
            
            if not self.sender_email or not self.sender_password:
                raise ValueError("Email credentials not found in password.ini file")
        except Exception as e:
            logging.error(f"Error loading email credentials: {e}")
            raise
            
    def send_item_notification(self, item):
        subject = self.subject_template.format(
            item_title=item['title'],
            price=item['price']
        )
        
        location = item.get('location', 'Unknown location')
        message_text = self.message_template.format(
            item_title=item['title'],
            price=item['price'],
            location=location,
            url=item['url']
        )
        
        return self._send_email(subject, message_text)
    
    def send_error_notification(self, error_message):
        subject = "ERROR: Facebook Marketplace Scraper"
        message_text = f"The marketplace scraper encountered an error at {datetime.now()}:\n\n{error_message}\n\nThe scraper has been deactivated. Please check the logs and restart manually."
        
        return self._send_email(subject, message_text)
    
    def _send_email(self, subject, message_text):
        try:
            message = MIMEMultipart()
            message['Subject'] = subject
            message['From'] = self.sender_email
            message['To'] = self.recipient_email
            
            message.attach(MIMEText(message_text, 'plain'))
            
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, self.recipient_email, message.as_string())
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.sender_email, self.sender_password)
                    server.sendmail(self.sender_email, self.recipient_email, message.as_string())
                
            logging.info(f"Email notification sent: {subject}")
            return True
        
        except Exception as e:
            logging.error(f"Failed to send email notification: {e}")
            return False

    def test_connection(self):
        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                    server.login(self.sender_email, self.sender_password)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(self.sender_email, self.sender_password)
            
            logging.info("SMTP connection test successful")
            return True
        except Exception as e:
            logging.error(f"SMTP connection test failed: {e}")
            return False

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    try:
        notifier = EmailNotifier({})
        
        connection_test = notifier.test_connection()
        if not connection_test:
            print("Email is = ", notifier.sender_email)
            print("Password is = ", notifier.sender_password)
            print("Failed to connect to SMTP server. Check credentials and server settings.")
            exit(1)
        
        test_config = {
            'recipient_email': notifier.sender_email,
        }
        notifier.recipient_email = notifier.sender_email
        
        test_item = {
            'title': 'Test Product',
            'price': 199.99,
            'location': 'Test Location',
            'url': 'https://example.com/test-product'
        }
        
        success = notifier.send_item_notification(test_item)
        
        if success:
            print("Test email sent successfully!")
        else:
            print("Failed to send test email.")

            
    except Exception as e:
        print(f"Error during test: {e}")