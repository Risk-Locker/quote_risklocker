-- Add replacement_title to company_benefit_conditions
ALTER TABLE company_benefit_conditions
ADD COLUMN replacement_title VARCHAR(255);
