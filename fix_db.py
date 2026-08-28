import sys
sys.path.append('backend')
from app.db.session import SessionLocal
from sqlalchemy import text

db = SessionLocal()
print("Connected to DB.")
db.execute(text("UPDATE catalog_offerings SET display_value = 'RM2,000' WHERE display_value ILIKE '%Court legal defense costs coverage up to RM2,000%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = 'RM3,000' WHERE display_value ILIKE '%Court legal defense costs coverage up to RM3,000%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = '3 years' WHERE display_value ILIKE '%3-year panel workshop repair workmanship warranty%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = '365km' WHERE display_value ILIKE '%Towing 365km + tolls%' OR display_value ILIKE '%365km Round Trip%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = '50km' WHERE display_value ILIKE '%Towing 50km + tolls%' OR display_value ILIKE '%50km Round Trip%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = 'Unlimited' WHERE display_value ILIKE '%Unlimited towing%' OR display_value ILIKE '%Unlimited round trip%' OR display_value ILIKE '%unlimited%'"))
db.execute(text("UPDATE catalog_offerings SET display_value = 'RM 3,000' WHERE display_value ILIKE '%RM 3,000 payable upon flood%' OR display_value ILIKE '%RM3,000 Flood Cash%' OR label_override = 'Flood Relief Cash Allowance'"))
db.commit()
print("Updated successfully.")
