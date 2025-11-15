#!/bin/bash

echo "=== Checking API Stats ==="
curl -s https://rag-chatbot-501013051271.asia-southeast1.run.app/api-stats | python3 -m json.tool

echo ""
echo "=== Checking Cache Stats ==="
curl -s https://rag-chatbot-501013051271.asia-southeast1.run.app/cache/stats | python3 -m json.tool

echo ""
echo "=== Checking Health ==="
curl -s https://rag-chatbot-501013051271.asia-southeast1.run.app/health | python3 -m json.tool
