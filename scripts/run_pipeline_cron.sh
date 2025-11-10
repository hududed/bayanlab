#!/bin/bash
#
# Automated pipeline runner for cron
# Runs the BayanLab data pipeline with error handling and notifications
#
# Usage: ./scripts/run_pipeline_cron.sh [events|businesses|all]
#
# Cron setup (every 4 hours):
#   0 */4 * * * cd /path/to/bayanlab && ./scripts/run_pipeline_cron.sh all >> logs/cron.log 2>&1

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
PIPELINE_TYPE="${1:-all}"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOG_DIR/pipeline_${PIPELINE_TYPE}_${TIMESTAMP}.log"

# Email notification settings (optional - set these environment variables)
SEND_EMAIL="${SEND_EMAIL:-false}"
EMAIL_TO="${EMAIL_TO:-}"
EMAIL_FROM="${EMAIL_FROM:-noreply@bayanlab.com}"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Function to send email notification on failure
send_failure_email() {
    local exit_code=$1
    local log_file=$2

    if [[ "$SEND_EMAIL" == "true" && -n "$EMAIL_TO" ]]; then
        local subject="[BayanLab] Pipeline Failed - $PIPELINE_TYPE (exit code: $exit_code)"
        local body="Pipeline execution failed at $(date)

Exit Code: $exit_code
Pipeline Type: $PIPELINE_TYPE
Log File: $log_file

Last 50 lines of log:
$(tail -n 50 "$log_file")
"

        # Use mail command if available
        if command -v mail &> /dev/null; then
            echo "$body" | mail -s "$subject" "$EMAIL_TO"
        elif command -v sendmail &> /dev/null; then
            echo -e "Subject: $subject\nFrom: $EMAIL_FROM\nTo: $EMAIL_TO\n\n$body" | sendmail "$EMAIL_TO"
        else
            echo "ERROR: No mail command available for email notifications" >&2
        fi
    fi
}

# Log startup
echo "========================================" | tee -a "$LOG_FILE"
echo "BayanLab Pipeline Cron Job" | tee -a "$LOG_FILE"
echo "Started at: $(date)" | tee -a "$LOG_FILE"
echo "Pipeline type: $PIPELINE_TYPE" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Change to project directory
cd "$PROJECT_ROOT"

# Check if database is accessible
if ! PGPASSWORD=bayan psql -h localhost -p 5433 -U bayan -d bayan_backbone -c '\q' 2>/dev/null; then
    echo "ERROR: Cannot connect to database on localhost:5433" | tee -a "$LOG_FILE"
    send_failure_email 1 "$LOG_FILE"
    exit 1
fi

# Run the pipeline
echo "Running pipeline: uv run python run_pipeline.py --pipeline $PIPELINE_TYPE" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

if uv run python run_pipeline.py --pipeline "$PIPELINE_TYPE" 2>&1 | tee -a "$LOG_FILE"; then
    EXIT_CODE=0
    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "Pipeline completed successfully" | tee -a "$LOG_FILE"
    echo "Finished at: $(date)" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"
    echo "ERROR: Pipeline failed with exit code $EXIT_CODE" | tee -a "$LOG_FILE"
    echo "Finished at: $(date)" | tee -a "$LOG_FILE"
    echo "========================================" | tee -a "$LOG_FILE"

    # Send failure notification
    send_failure_email "$EXIT_CODE" "$LOG_FILE"
fi

# Clean up old log files (keep last 30 days)
find "$LOG_DIR" -name "pipeline_*.log" -type f -mtime +30 -delete 2>/dev/null || true

exit $EXIT_CODE
