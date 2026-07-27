
Thanks for the detailed answers. I reviewed the reference images — the template is clear: header with insurer logo, coverage table, payment box, “Our Specials” cards with icons and bilingual text, then “You May Add On”.
Before I write `prompts.md`, I still need clarity on a few structural points. These will decide the menu layout and database schema.
## Remaining questions
### 1. Top-level menu layout
You mentioned **Personalization**, **Settings**, **Extraction**, and **Builder**. Here is my best guess of where each existing/current admin feature should go. Please confirm or correct: 
- **Personalization** (confirmed correct)
  - Users & Roles
  - Per-user activity logs
  - Active sessions / active users
  - Failed-login security logs
- **Builder**(confirmed correct just the starting wil be insurance companies, then our specials then templates though it doesnt matter but still i am just talking about the visual aspect only)
  - Templates
  - Our Specials
  - Insurance Companies
- **Settings**(confirmed correct)
  - System Checks
  - Storage
  - Extraction settings
  - Field aliases
  - Vehicle brands/models
  - Road-tax reference data
- **Extraction**( this one i dont get it. cause what will happen to uploads then?? i wanted the upload flow that is present currently to be present and it will work like new sessions thats it. if user creates a new session and uploads nothing then that session wont be saved. only upon uploading and proceeding will make a difference )

(for the extraction part i asked you to create is a setting part for the part 1 features or customiztion there caus stuffs including uploading relevant datasets like words that the pdf extractor will match into will be uploaded here like NCD can non claimable discount or no claim dic or more. so any words simmilar will reference to ncd. any other logics like how will the roadtax be calcualed to a raodtax table will be added so upon extracting the cc it iwll add the road tax as well. proper logics will be added  example :
2. Peninsular Malaysia Road Tax by CC
A. Private Saloon Car, Individual Owner, Peninsular Malaysia

Use this for normal private cars like Myvi, Axia, Saga, Bezza, City, Vios, Civic sedan, Camry sedan, etc. JPJ lists this as Motokar Saloon Persendirian Milik Individu, code AB.

Engine capacity	Road tax rate1,000cc and below	RM20
1,001cc to 1,200cc	RM55
1,201cc to 1,400cc	RM70
1,401cc to 1,600cc	RM90
1,601cc to 1,800cc	RM200 + RM0.40 per cc above 1,600cc
1,801cc to 2,000cc	RM280 + RM0.50 per cc above 1,800cc
2,001cc to 2,500cc	RM380 + RM1.00 per cc above 2,000cc
2,501cc to 3,000cc	RM880 + RM2.50 per cc above 2,500cc
Above 3,000cc	RM2,130 + RM4.50 per cc above 3,000cc

Example: a 1,500cc private saloon in Peninsular Malaysia is RM90/year. A 1,999cc private saloon is RM280 + (199cc × RM0.50) = RM379.50, normally rounded/charged by JPJ at renewal.

B. Saloon Car, Company Registered, Peninsular Malaysia

Use this if the car is registered under a company name and the body type is saloon. JPJ lists this as Motokar Saloon Persendirian Milik Syarikat, code AC.

Engine capacity	Road tax rate1,000cc and below	RM20
1,001cc to 1,200cc	RM110
1,201cc to 1,400cc	RM140
1,401cc to 1,600cc	RM180
1,601cc to 1,800cc	RM400 + RM0.80 per cc above 1,600cc
1,801cc to 2,000cc	RM560 + RM1.00 per cc above 1,800cc
2,001cc to 2,	RM760 + RM3.00 per cc above 2,000cc
2,501cc to 3,000cc	RM2,260 + RM7.50 per cc above 2,500cc
Above 3,000cc	RM6,010 + RM13.50 per cc above 3,000cc

Company-registered saloon cars can be much more expensive than individual private saloon cars, especially above 2,000cc.

C. Non-Saloon Vehicle, Individual or Company, Peninsular Malaysia

Use this for SUV, MPV, pick-up, 4x4, and similar non-saloon vehicles. JPJ lists this as private vehicle other than saloon, for both individual and company categories.

Engine capacity	Road tax rate1,000cc and below	RM20
1,001cc to 1,200cc	RM85
1,201cc to 1,400cc	RM100
1,401cc to 1,600cc	RM120
1,601cc to 1,800cc	RM300 + RM0.30 per cc above 1,600cc
1,801cc to 2,000cc	RM360 + RM0.40 per cc above 1,800cc
2,001cc to 2,500cc	RM440 + RM0.80 per cc above 2,000cc
2,501cc to 3,000cc	RM840 + RM1.60 per cc above 2,500cc
Above 3,000cc	RM1,640 + RM1.60 per cc above 3,000cc

This is why a large SUV or pick-up may sometimes have lower road tax than a large-engine saloon in Peninsular Malaysia.

3. Sabah and Sarawak Road Tax

Sabah and Sarawak use lower road tax rates than Peninsular Malaysia, and JPJ’s official LKM guide covers separate calculation for Peninsular Malaysia, Sabah and Sarawak.

For a quick reference, many common private passenger cars in Sabah/Sarawak are lower than Peninsular Malaysia. For example, a 1.5L Perodua Alza/Aruz is shown as RM90 in Peninsular Malaysia and RM56 in Sabah/Sarawak in a 2025 updated road tax comparison.

Engine / vehicle example	Peninsular private saloon reference	Sabah/Sarawak typical lower rate1,000cc and below	RM20	RM20
1,001cc to 1,200cc	RM55	Lower than Peninsular, commonly around RM44 for private saloon references
1,201cc to 1,400cc	RM70	Lower than Peninsular, commonly around RM56 for private saloon references
1,401cc to 1,600cc	RM90	Lower than Peninsular, commonly around RM72 or RM56 depending body/category reference
Above	Progressive formula	Lower progressive structure than Peninsular

Because East Malaysia tables vary by body type and registration class, the safest exact amount should be checked through JPJ/MyJPJ or a JPJ-compliant road tax calculator using vehicle location, body type, ownership type and engine cc. JPJ’s newer documents also state renewal charges follow CC and class of use, not just cc alone.

4. Langkawi, Pangkor and Labuan

Langkawi, Pangkor and Labuan have special duty-free island treatment. Road tax references show that cars up to 1,000cc are generally RM20, while vehicles above 1,000cc use discounted rates compared with Peninsular Malaysia.

Private Saloon, Langkawi / Pangkor reference
Engine capacity	Road tax rateBelow / up to 1,000cc	RM20
1,001cc to 1,200cc	RM27.50
1,201cc to 1,400cc	RM35
1,401cc to 1,600cc	RM45
1,601cc to 1,800	RM100 + RM0.20 per cc above 1,600cc
1,801cc to 2,000cc	RM140 + RM0.25 per cc above 1,800cc
2,001cc to 2,	RM190 + RM0.50 per cc above 2,000cc
2,501cc to 3,000cc	RM440 + RM0.75 per cc above 2,500cc
Above 3,000cc	Discounted island formula, usually based on reduced Peninsular rate

The source table for Langkawi/Pangkor shows private saloon rates such as RM27.50 for 1,001 to 1,200cc, RM45 for 1,401 to 1,600cc, and progressive charges after 1,600cc.

5. Motorcycle Road Tax by CC, Peninsular Malaysia

JPJ’s official LKM guide lists fixed motorcycle rates for motorcycles above 150cc, and 2026 road tax guides list the common Peninsular table including the 150cc-and-below tier.

Motorcycle engine capacity	Road tax rate150cc and below	RM2
151cc to 200cc	RM30
201cc to 250cc	RM50
251cc to 500cc	RM180
501cc to 800cc	RM250
Above 800cc	RM350

also for var names and models as well so that if written beza it should get perodua bezza original full model name so the extraction be more correct and easy

 )
  - Upload / new session
  - Session list (like ChatGPT chats)
  - Review/edit extracted values
Is this correct, or did you imagine Builder / Settings / Personalization differently?
### 2. Default insurance companies (confirmed correct)
You said “keep exactly the 6 insurances” and then listed 8 names. I need a final answer:
- Are the **locked default companies** exactly these 6: **QBE, AmGen, Liberty, STMB, Tune, Etiqa**?
- **Lonpac** and **Sompo** are not defaults, but users can add them manually. Correct?
- The 6 defaults cannot be deleted, only disabled/renamed. Correct?
### 3. MAC address blocking (confirmed correct)
Browsers do not send MAC addresses in normal HTTP requests. We can reliably capture:
- IP address
- User-Agent
- A browser/device fingerprint
- Geolocation (if allowed by browser)
**Question:** Should we use a **device fingerprint** instead of MAC, or do you have a network-level way to read MAC that I should know about?
### 4. “Session” entity
Currently one upload = one `UploadedFile` + one `QuotationDraft`.
For the ChatGPT-like session model, do we need a new `Session` table that groups uploads, or is **one upload = one session** good enough?
Important because it changes migration/schema work.
### 5. Builder landing page
When a user opens **Builder**, what should they see?
Option A: A dashboard with tabs/cards for:
- Templates
- Our Specials
- Insurance Companies
Option B: Separate sidebar items under Builder: (this one)
- Builder → Templates
- Builder → Our Specials
- Builder → Companies
Which one matches your vision?
### 6. PDF preview output format (confirmed correct)
You said the final output can be **image or PDF**. In the preview/editor step, should the browser show:
- A rendered **image (PNG/JPG)** that can be downloaded as PDF?
- The actual **PDF** rendered inline?
- Both? (simply add an option to export as pdf or png thats it.)
### 7. Old prompts to keep (confirmed)
Some old prompts cover features we still need:
- Configurable extraction-field registry
- Vehicle brands/models and road-tax reference data
- Template library / builder precision
- History, trash, PDF storage
- API hardening / Pydantic schemas / tests
Should I merge these into the new phase list under the appropriate sections, or do you want to drop any of them?
### 8. Login notifications(confirmed)
When someone logs in, **all staff and dev** get an in-app notification. Should this include the user’s email, IP, time, and device info?
### 9. Active users “kick”(confirmed correct)
Kicking a user = revoking all their sessions immediately. Only admin/super admin can do it. Correct?
### 10. Prompt skills(confirmed)
The current environment only has the `customize-opencode` skill available. The old prompts list project-local skills that may not exist. Should I:
- Drop “Required skills” entirely, or
- Keep it minimal and only mention a skill if it is actually built into this repo?
---
Once you answer these, I will write the complete `prompts.md` as a linear, unit-wise plan with “Done / Finished” markers and no skill bloat.