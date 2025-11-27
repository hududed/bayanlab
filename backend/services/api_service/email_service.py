"""
Email service for sending confirmation emails via SendGrid
"""
import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from backend.services.common.config import get_settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SendGrid"""

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.sendgrid_api_key
        self.from_email = settings.sendgrid_from_email
        self.from_name = settings.sendgrid_from_name
        self.reply_to = settings.sendgrid_reply_to
        self.admin_email = settings.admin_email  # Add admin email from config

        if not self.api_key:
            logger.warning("SENDGRID_API_KEY not set - email sending will be disabled")
            self.enabled = False
        else:
            self.enabled = True
            self.client = SendGridAPIClient(self.api_key)

    async def send_claim_confirmation(
        self,
        to_email: str,
        owner_name: str,
        business_name: str,
        claim_id: str
    ) -> bool:
        """
        Send confirmation email when a business claim is submitted

        Args:
            to_email: Recipient email address
            owner_name: Name of the business owner
            business_name: Name of the business
            claim_id: Unique claim ID

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Email service is disabled - skipping email send")
            return False

        try:
            # Create the email content
            subject = f"Business Claim Received - {business_name}"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 28px; font-weight: 700;">
                                ✅ Claim Received!
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px; color: #1f2937; font-size: 16px; line-height: 1.6;">
                                As-salamu alaykum <strong>{owner_name}</strong>,
                            </p>

                            <p style="margin: 0 0 20px; color: #1f2937; font-size: 16px; line-height: 1.6;">
                                JazakAllah khair for submitting <strong>{business_name}</strong> to ProWasl! 🎉
                            </p>

                            <div style="background-color: #f0fdf4; border-left: 4px solid #10b981; padding: 20px; margin: 30px 0; border-radius: 8px;">
                                <p style="margin: 0 0 10px; color: #065f46; font-size: 14px; font-weight: 600;">
                                    📋 CLAIM ID
                                </p>
                                <p style="margin: 0; color: #047857; font-size: 18px; font-weight: 700; font-family: 'Courier New', monospace;">
                                    {claim_id}
                                </p>
                            </div>

                            <h2 style="margin: 30px 0 15px; color: #1f2937; font-size: 20px; font-weight: 600;">
                                What happens next?
                            </h2>

                            <ul style="margin: 0 0 30px; padding-left: 25px; color: #4b5563; font-size: 15px; line-height: 1.8;">
                                <li style="margin-bottom: 10px;">Our team will review your submission (usually within 24-48 hours)</li>
                                <li style="margin-bottom: 10px;">We'll verify the business information you provided</li>
                                <li style="margin-bottom: 10px;">Once approved, your business will appear on ProWasl.com</li>
                                <li style="margin-bottom: 10px;">You'll receive another email when your listing goes live insha'Allah</li>
                            </ul>

                            <div style="background-color: #eff6ff; padding: 20px; border-radius: 8px; margin: 30px 0;">
                                <p style="margin: 0 0 10px; color: #1e40af; font-size: 15px; font-weight: 600;">
                                    💡 In the meantime...
                                </p>
                                <p style="margin: 0; color: #1e3a8a; font-size: 14px; line-height: 1.6;">
                                    Help us grow! Share ProWasl with other Muslim business owners in your network. The stronger our directory, the better we can serve our community.
                                </p>
                            </div>

                            <p style="margin: 30px 0 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                                Questions? Just reply to this email - I read every message!
                            </p>

                            <p style="margin: 20px 0 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                                BarakAllahu feek,<br>
                                <strong style="color: #1f2937;">{self.from_name}</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 10px; color: #6b7280; font-size: 13px;">
                                ProWasl - Connecting Muslims with Halal Businesses
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                                This email was sent because you submitted a business claim at claim.prowasl.com
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

            # Plain text version
            text_content = f"""
As-salamu alaykum {owner_name},

JazakAllah khair for submitting {business_name} to ProWasl!

CLAIM ID: {claim_id}

What happens next?
- Our team will review your submission (usually within 24-48 hours)
- We'll verify the business information you provided
- Once approved, your business will appear on ProWasl.com
- You'll receive another email when your listing goes live insha'Allah

In the meantime, help us grow! Share ProWasl with other Muslim business owners in your network.

Questions? Just reply to this email - I read every message!

BarakAllahu feek,
{self.from_name}

---
ProWasl - Connecting Muslims with Halal Businesses
This email was sent because you submitted a business claim at claim.prowasl.com
"""

            # Create the message
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            # Set reply-to
            message.reply_to = Email(self.reply_to)

            # Send the email
            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Confirmation email sent to {to_email} for claim {claim_id}")
                return True
            else:
                logger.error(f"Failed to send email. Status: {response.status_code}, Body: {response.body}")
                return False

        except Exception as e:
            logger.error(f"Error sending confirmation email: {e}")
            return False

    async def send_admin_notification(
        self,
        business_name: str,
        owner_name: str,
        owner_email: str,
        city: str,
        state: str,
        claim_id: str
    ) -> bool:
        """
        Send notification to admin when a new business claim is submitted

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.enabled or not self.admin_email:
            logger.warning("Admin notification disabled - no admin email configured")
            return False

        try:
            subject = f"🔔 New Business Claim: {business_name}"

            html_content = f"""
<!DOCTYPE html>
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background-color: #f5f5f5;">
    <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px;">
        <h2 style="color: #1f2937; margin-top: 0;">🔔 New Business Claim Submitted</h2>

        <div style="background: #f0fdf4; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0;">
            <p style="margin: 0; font-weight: bold; font-size: 18px; color: #047857;">{business_name}</p>
            <p style="margin: 5px 0 0; color: #065f46;">{city}, {state}</p>
        </div>

        <h3 style="color: #1f2937;">Owner Details</h3>
        <ul style="color: #4b5563; line-height: 1.8;">
            <li><strong>Name:</strong> {owner_name}</li>
            <li><strong>Email:</strong> {owner_email}</li>
            <li><strong>Claim ID:</strong> <code>{claim_id}</code></li>
        </ul>

        <div style="background: #eff6ff; padding: 15px; border-radius: 6px; margin-top: 25px;">
            <p style="margin: 0; color: #1e40af; font-weight: 600;">👉 Action Required</p>
            <p style="margin: 10px 0 0; color: #1e3a8a; font-size: 14px;">
                Run <code>uv run python scripts/review_claims.py</code> to review and approve this claim.
            </p>
        </div>
    </div>
</body>
</html>
"""

            text_content = f"""
New Business Claim Submitted

Business: {business_name}
Location: {city}, {state}

Owner Details:
- Name: {owner_name}
- Email: {owner_email}
- Claim ID: {claim_id}

Action Required:
Run 'uv run python scripts/review_claims.py' to review and approve this claim.
"""

            message = Mail(
                from_email=Email(self.from_email, "ProWasl Claims"),
                to_emails=To(self.admin_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Admin notification sent for claim {claim_id}")
                return True
            else:
                logger.error(f"Failed to send admin notification. Status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending admin notification: {e}")
            return False

    async def send_discovery_notification(
        self,
        to_email: str,
        business_name: str,
        city: str,
        state: str,
        claim_id: str
    ) -> bool:
        """
        Send notification to business owners we discovered from external sources.

        This is for businesses we've added from directories like MBC - letting them
        know their business is now listed and inviting them to claim/update it.

        Args:
            to_email: Business contact email
            business_name: Name of the business
            city: Business city
            state: Business state
            claim_id: Unique claim ID for reference

        Returns:
            True if email was sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning("Email service is disabled - skipping discovery email")
            return False

        try:
            subject = f"Your business {business_name} is now on ProWasl!"

            html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
    <table role="presentation" style="width: 100%; border-collapse: collapse;">
        <tr>
            <td style="padding: 40px 20px;">
                <table role="presentation" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%); padding: 40px 30px; text-align: center;">
                            <h1 style="margin: 0; color: #ffffff; font-size: 26px; font-weight: 700;">
                                We Found Your Business!
                            </h1>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <p style="margin: 0 0 20px; color: #1f2937; font-size: 16px; line-height: 1.6;">
                                As-salamu alaykum,
                            </p>

                            <p style="margin: 0 0 20px; color: #1f2937; font-size: 16px; line-height: 1.6;">
                                Great news! We discovered <strong>{business_name}</strong> in {city}, {state} and have added it to <strong>ProWasl</strong> - a directory connecting the Muslim community with trusted businesses.
                            </p>

                            <div style="background-color: #f0f9ff; border-left: 4px solid #3b82f6; padding: 20px; margin: 30px 0; border-radius: 8px;">
                                <p style="margin: 0 0 10px; color: #1e40af; font-size: 14px; font-weight: 600;">
                                    YOUR LISTING REFERENCE
                                </p>
                                <p style="margin: 0; color: #1d4ed8; font-size: 18px; font-weight: 700; font-family: 'Courier New', monospace;">
                                    {claim_id}
                                </p>
                            </div>

                            <h2 style="margin: 30px 0 15px; color: #1f2937; font-size: 20px; font-weight: 600;">
                                What this means for you
                            </h2>

                            <ul style="margin: 0 0 30px; padding-left: 25px; color: #4b5563; font-size: 15px; line-height: 1.8;">
                                <li style="margin-bottom: 10px;">Your business is now visible to Muslims looking for trusted services</li>
                                <li style="margin-bottom: 10px;">Community members can find you on prowasl.com</li>
                                <li style="margin-bottom: 10px;">No action needed - your listing is already live!</li>
                            </ul>

                            <div style="background-color: #fefce8; padding: 20px; border-radius: 8px; margin: 30px 0;">
                                <p style="margin: 0 0 10px; color: #854d0e; font-size: 15px; font-weight: 600;">
                                    Want to update your listing?
                                </p>
                                <p style="margin: 0; color: #713f12; font-size: 14px; line-height: 1.6;">
                                    If any information is incorrect or you'd like to add more details, simply reply to this email with your updates. We're happy to help!
                                </p>
                            </div>

                            <p style="margin: 30px 0 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                                Questions or concerns? Just reply to this email.
                            </p>

                            <p style="margin: 20px 0 0; color: #4b5563; font-size: 15px; line-height: 1.6;">
                                BarakAllahu feek,<br>
                                <strong style="color: #1f2937;">The ProWasl Team</strong>
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9fafb; padding: 30px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0 0 10px; color: #6b7280; font-size: 13px;">
                                ProWasl - Connecting Muslims with Halal Businesses
                            </p>
                            <p style="margin: 0; color: #9ca3af; font-size: 12px;">
                                Your business was discovered through a Muslim business directory.<br>
                                If you'd like to be removed, simply reply to this email.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

            text_content = f"""
As-salamu alaykum,

Great news! We discovered {business_name} in {city}, {state} and have added it to ProWasl - a directory connecting the Muslim community with trusted businesses.

YOUR LISTING REFERENCE: {claim_id}

What this means for you:
- Your business is now visible to Muslims looking for trusted services
- Community members can find you on prowasl.com
- No action needed - your listing is already live!

Want to update your listing?
If any information is incorrect or you'd like to add more details, simply reply to this email with your updates. We're happy to help!

Questions or concerns? Just reply to this email.

BarakAllahu feek,
The ProWasl Team

---
ProWasl - Connecting Muslims with Halal Businesses
Your business was discovered through a Muslim business directory.
If you'd like to be removed, simply reply to this email.
"""

            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )

            message.reply_to = Email(self.reply_to)

            response = self.client.send(message)

            if response.status_code in [200, 201, 202]:
                logger.info(f"Discovery email sent to {to_email} for business {business_name}")
                return True
            else:
                logger.error(f"Failed to send discovery email. Status: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error sending discovery email: {e}")
            return False


# Singleton instance
email_service = EmailService()
