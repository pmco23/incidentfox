#!/bin/bash
set -e

# Test Template System Locally
# This script:
# 1. Runs migration locally
# 2. Seeds templates locally
# 3. Starts services locally

echo "========================================="
echo "Template System Local Testing"
echo "========================================="
echo ""

# Color codes
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo -e "${YELLOW}⚠️  DATABASE_URL is not set${NC}"
    echo "Please set DATABASE_URL to your local or remote database"
    echo "Example: export DATABASE_URL='postgresql://user:pass@localhost:5432/dbname'"
    exit 1
fi

# Step 1: Run migration
echo -e "${BLUE}Step 1: Running database migration...${NC}"
cd config_service
alembic upgrade head
echo -e "${GREEN}✓ Migration completed${NC}"
echo ""

# Step 2: Seed templates
echo -e "${BLUE}Step 2: Seeding templates...${NC}"
python scripts/seed_templates.py
echo -e "${GREEN}✓ Templates seeded (check output above for count)${NC}"
cd ..
echo ""

# Step 3: Verify templates in database
echo -e "${BLUE}Step 3: Verifying templates in database...${NC}"
cd config_service
python -c "
from sqlalchemy import create_engine, text
import os
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM templates'))
    count = result.scalar()
    print(f'Templates in database: {count}')

    result = conn.execute(text('SELECT name, use_case_category FROM templates ORDER BY id'))
    print('\nTemplates:')
    for row in result:
        print(f'  - {row[0]} ({row[1]})')
"
cd ..
echo -e "${GREEN}✓ Verification complete${NC}"
echo ""

# Step 4: Instructions for starting services
echo "========================================="
echo -e "${GREEN}✓ Local Setup Complete!${NC}"
echo "========================================="
echo ""
echo "To start services locally:"
echo ""
echo "Terminal 1 - Config Service:"
echo "  cd config_service"
echo "  uvicorn src.api.main:app --reload --port 8080"
echo ""
echo "Terminal 2 - Web UI:"
echo "  cd web_ui"
echo "  npm run dev"
echo ""
echo "Then open: http://localhost:3000/team/templates"
echo ""
