#!/bin/bash
#
# VPS Deployment Script for Sri Lanka Tender Hub
# Run this on your Ubuntu/Debian VPS to set up the 24/7 service
#
set -e

echo "=========================================="
echo " Sri Lanka Tender Hub - VPS Setup"
echo "=========================================="

# Install system dependencies
echo "📦 Installing system packages..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Create application directory
APP_DIR="/opt/sl-tender-hub"
echo "📂 Setting up application at $APP_DIR..."
sudo mkdir -p $APP_DIR
sudo cp -r ../* $APP_DIR/
cd $APP_DIR

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service for API server
echo "⚙️  Creating systemd service for API server..."
sudo tee /etc/systemd/system/sl-tender-hub-api.service > /dev/null <<EOF
[Unit]
Description=Sri Lanka Tender Hub API Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=$APP_DIR
Environment="PATH=$APP_DIR/venv/bin"
ExecStart=$APP_DIR/venv/bin/python $APP_DIR/api.py
Restart=always
RestartSec=5
MemoryMax=256M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

# Enable and start API service
echo "🚀 Starting API server..."
sudo systemctl daemon-reload
sudo systemctl enable sl-tender-hub-api
sudo systemctl start sl-tender-hub-api

# Set up daily cron job for scraping (Priority 1 daily at 2AM, Priority 2 every 3 days, Priority 3 weekly)
echo "⏰ Setting up scheduled scraping..."
CRON_FILE="/etc/cron.d/sl-tender-hub-scraper"
sudo tee $CRON_FILE > /dev/null <<EOF
# Sri Lanka Tender Hub - Scheduled scraping jobs
# Priority 1 sites (major portals): Daily at 2 AM
0 2 * * * root cd $APP_DIR && $APP_DIR/venv/bin/python run_scraper.py 1 >> /var/log/sl-tender-hub.log 2>&1
# Priority 2 sites (ministries/SOEs): Every 3 days at 3 AM
0 3 */3 * * root cd $APP_DIR && $APP_DIR/venv/bin/python run_scraper.py 2 >> /var/log/sl-tender-hub.log 2>&1
# Priority 3 sites (universities): Weekly on Sunday at 4 AM
0 4 * * 0 root cd $APP_DIR && $APP_DIR/venv/bin/python run_scraper.py 3 >> /var/log/sl-tender-hub.log 2>&1
EOF
sudo chmod 644 $CRON_FILE

# Create log file
sudo touch /var/log/sl-tender-hub.log
sudo chmod 644 /var/log/sl-tender-hub.log

# Optional: Set up nginx reverse proxy (uncomment if you want to expose via domain)
# echo "🌐 Setting up Nginx reverse proxy..."
# sudo apt install -y nginx
# sudo tee /etc/nginx/sites-available/sl-tender-hub > /dev/null <<EOF
# server {
#     listen 80;
#     server_name api.yourdomain.com;
#     location / {
#         proxy_pass http://127.0.0.1:8000;
#         proxy_set_header Host \$host;
#         proxy_set_header X-Real-IP \$remote_addr;
#     }
# }
# EOF
# sudo ln -s /etc/nginx/sites-available/sl-tender-hub /etc/nginx/sites-enabled/
# sudo nginx -t && sudo systemctl reload nginx

echo ""
echo "=========================================="
echo "✅ Deployment Complete!"
echo "=========================================="
echo ""
echo "📍 API Server running at: http://$(hostname -I | awk '{print $1}'):8000"
echo "📚 API Documentation (Swagger): http://$(hostname -I | awk '{print $1}'):8000/docs"
echo ""
echo "📊 Useful commands:"
echo "  Check API status: sudo systemctl status sl-tender-hub-api"
echo "  View API logs: sudo journalctl -u sl-tender-hub-api -f"
echo "  View scrape logs: tail -f /var/log/sl-tender-hub.log"
echo "  Run scraper manually: cd $APP_DIR && venv/bin/python run_scraper.py"
echo "  Database location: $APP_DIR/tenders.db"
echo ""
echo "💾 Memory limit set: 256MB per service (well within your 512MB target)"
echo ""
