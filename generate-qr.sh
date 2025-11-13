#!/bin/bash
# Generate QR code for the claim form
# Usage: ./generate-qr.sh <your-ngrok-url>

if [ -z "$1" ]; then
    echo "❌ Please provide your ngrok URL"
    echo ""
    echo "Usage: ./generate-qr.sh https://abc123.ngrok.io"
    echo ""
    echo "Steps:"
    echo "1. Run: ./deploy-ngrok.sh"
    echo "2. Copy the ngrok URL (e.g., https://abc123.ngrok.io)"
    echo "3. Run: ./generate-qr.sh https://abc123.ngrok.io"
    exit 1
fi

NGROK_URL=$1
CLAIM_URL="${NGROK_URL}/claim"

echo "🎨 Generating QR Code for Claim Form"
echo "======================================"
echo ""
echo "URL: $CLAIM_URL"
echo ""

# Check if qrencode is installed
if ! command -v qrencode &> /dev/null; then
    echo "📦 Installing qrencode..."
    brew install qrencode
fi

# Generate QR code (terminal version)
echo "QR Code (scan with phone):"
echo ""
qrencode -t ANSIUTF8 "$CLAIM_URL"
echo ""

# Generate PNG file
OUTPUT_FILE="claim_qr_code.png"
qrencode -o "$OUTPUT_FILE" -s 10 "$CLAIM_URL"

echo "✅ QR code saved to: $OUTPUT_FILE"
echo ""
echo "📋 Next Steps:"
echo "1. Open $OUTPUT_FILE"
echo "2. Print multiple copies for Saturday"
echo "3. Test scanning with your phone to verify"
echo ""
echo "🔗 Or use online generator:"
echo "   https://www.qr-code-generator.com/"
echo "   Enter URL: $CLAIM_URL"
echo ""
