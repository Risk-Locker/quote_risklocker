Users & Roles

Email
Password (min 8 characters)

Staff
Add user
admin@risklocker.local	super_admin	active	Revoke sessions
System Checks
Database provider
Supabase/Postgres
Ready
FastAPI
Ready
Ready
SQLAlchemy
Ready
Ready
PyMuPDF
Ready
Ready
pdfplumber
Ready
Ready
pikepdf
Ready
Ready
Playwright PDF rendering
Install Playwright and Chromium: python -m playwright install chromium
Needs Setup
Supabase PDF storage
Private bucket 'risklocker-pdfs' is ready.
Ready
PDF malware scanner
Microsoft Defender is available.
Ready
PaddleOCR enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
OpenCV visual checks
Optional enhanced reading feature unavailable.
Unavailable
Tesseract enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
OCRmyPDF enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
Database
Database connection is working.
Ready
Insurance Companies
Company display name
Save company
Template Settings
Template name
Save template
Benefits / Add-ons

The company section under admin http://127.0.0.1:3000/admin.

Okay first thing and most important thing now is i realized the admin and dev can only change templates or edit here. so listen instead of naming it admin or admin panel.  name this whole section a totally seprate place as it is but name the whole thing customize.
Now for the users tab only the users stuffs will be there not the rest of the things. cause it looks absolutely messy. Same for the other tabs as well. each tab only contain features of that tab nothing else.

Admin
Manage users, insurance companies, templates, benefits, and system checks.

Refresh
Users
Companies
Templates
Benefits
Storage
System Checks
Users & Roles
Email
Password (min 8 characters)

Staff
Add user
admin@risklocker.local	super_admin	active	Revoke sessions
System Checks
Database provider
Supabase/Postgres
Ready
FastAPI
Ready
Ready
SQLAlchemy
Ready
Ready
PyMuPDF
Ready
Ready
pdfplumber
Ready
Ready
pikepdf
Ready
Ready
Playwright PDF rendering
Install Playwright and Chromium: python -m playwright install chromium
Needs Setup
Supabase PDF storage
Private bucket 'risklocker-pdfs' is ready.
Ready
PDF malware scanner
Microsoft Defender is available.
Ready
PaddleOCR enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
OpenCV visual checks
Optional enhanced reading feature unavailable.
Unavailable
Tesseract enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
OCRmyPDF enhanced reading
Optional enhanced reading feature unavailable.
Unavailable
Database
Database connection is working.
Ready
Insurance Companies
Company display name
Save company
Template Settings
Template name
Save template
Benefits / Add-ons

For templates page there will be two sepearted option like a proepr arranged dasboard type UI. so i the templates will be in one side. there can be as well groups that can be created where each templates user wants can properly distribute.

so what i want is the the builder open currentyl is there which is okay but clicking that will open a new fresh template. not this default ones. noe if someone want to scopy anothher template there they can from the builder page.

So it will work exactly like canva but based on just our necessities.

the benefits part first of all change the benefits name to Our Specials.

(Let me give you a first level or admin level concept here and make you understand what is this systems main goal is. So RiskLocker is an agency that handles multiple insurances. so what they do is based on a clients situation and everything chooses the best insurance they can go with. so lets say as you can see there are mainly )

STMB

Motor · STMB · active

Liberty

Motor · Liberty · active

Etiqa Takaful

Motor · Etiqa Takaful · active

AIG

Motor · AIG · active

Kurnia

Motor · Kurnia · active

MMIP

Motor · MMIP · active

Other / Unknown

Motor · Other / Unknown · active

QBE-DPP

Motor · QBE-DPP · active

QBE

Motor · QBE · active

AmGen

Motor · Amgen / AmAssurance / Kurnia-style · active

AmAssurance

Motor · Amgen / AmAssurance / Kurnia-style · active

Now here mainly there are this only insurances :

| QBE     |
| ------- |
| AmGen   |
| Liberty |
| STMB    |
| Tune    |
| Etiqa   |
| Lonpac  |
| Sompo   |

So whatever insurance is best is compared first and this comparison it is done manually. so the comparison of alll this companies are done manually using the website to generate quotation. now after company is fixed that quotation will just be uploaded here. now since the client is basically Risklockers and risklocker is the middle man here so risklocker basically generates its own version of the quotation based on the insurance that is provded and then the process you know already which is this system does. )

Also there will be an option which is to just select a template and there is no need of selecting after text extraction. so that part remove it completely.

Why let me tell you. during template selection that template selected already will have all the things selected. so there is no need to choose there.

so simply the desired template will be selected and the values that are extracted will just get replaced and thats it.

So benefits are the benefits they are getting here and even though 90% cases this will be the benefits : Windscreen

Motor Benefits · active
Towing
Motor Benefits · active
All Drivers
Motor Benefits · active
Flood
Motor Benefits · active
Special Perils
Motor Benefits · active

but the problem here is the way the benefits(Our specials  will be shown should be interactive with a proper logo or small svg with that towing text.
So we need to manually edit each of the benefits(Our Specials) first here.

Listen for benefits(Our Specials) the canvas will not be a big one or even big the concept is to position simply the logo and the text in a proper way the staff wants. so it will form a simple image and text. now when in template creation mode they will not thing what will the benefits(Our Specials) towing look like, what will windscreen image look like and what texts can i add. do i make it circle or rectnagular. so all this will be fixed by the admin before they touch the templates builder.

Now i dont know how you can make a simple unified system for the builder part only.

cause what i think right now is the builder part needs to be present under customize but that will be a bit seperated and all building will be done there. and whatever we build there will show up properly during the template creation,

So if possible i think its better to make 2 sepearate tabs or menus one is probaly
personaliztion containing only users, system checks, setting and other stuffs not related to building or template building.

See the template building stuffs start just after texts are extracted. so lets say when a text is extracted and it found all the matches now. user either manually going to edit some and add some addons and pass it directly to the desiered template they want.

now this whole part till the final new pdf or png pdf version that will be found

next thing is the data uploading which will also be a totally seperate tab which will contains stuffs handlin the text uploading , to extraction, to proper sorting to propper company.

now what im saying is you have various ways to arrange things. you can hjust simply make a menu name

part 1- Extraction ---> so after everything confirmed in extraction part is done as in extraction of text part it will properly atleast need to know one thing which is under which company and insurance this will go though if it doesnt even know which one thats also fine as use can simple go through the insurance and just add it.

Now based on those companies the insurance copmany will appear or show up in builder. so any new insurance company will be shown there.

Now why im saying insurance company cause later in template we can select a company and make 1 or 3 or 10 or 100 copies of their insurance.

The other features that is going to be in here are going to be data uploading which will involce, CC to roadtax table along with viewing the current data list or comparison table its following, Vehicle car make and model no. data list and someo other logics that it might use.

same for the other lists like

part -2 Builder part is already told before or explained but shortly i will tell. The builder to me looks okay like the feratures are working and its understandable though got a few visual issues where if zoomed in too much  the viewport or the canvas crosses or ges broken so its still understandable just a simple visual flow.

bow another point which is

| QBE     |
| ------- |
| AmGen   |
| Liberty |
| STMB    |
| Tune    |
| Etiqa   |
| Lonpac  |
| Somp    |

there will only be 1 default template for each of this insurances. and the words that are used like premier, base etc... that is unnecessary.

cause in builder phase this are the companies will be seen since it will be set in part 1- Extraction tab. after that in thuis phase or phase 2 will have all the benfits listed.

now benefits are of 2 types. one is free of charge or simply default benefits you get just for purchasing. Now for addons normally the extras are towing, windshield and some others. now the concept here is after  creating all the benefits the user can have single group of version for each benefit with differnt names and values. why because in some cases lets say for the same benefit example "Compassionate allowance " this one is present in almost all the insurances options but for amgen maybe the same compassionate allowance going to be 3000RM, for another one is going to be 5000Rm or others. logo also might be different for the 5000 RM one...
so in this way each benefits will have suboptions as well. so during template creation simply based on the required benefits developer will just dragndrop the requiied one if its the amgen and needs to have 3000RM one will choose that one if 5000Rm one then that one.

So you understand me i hope the whole thing.

Also free of charge part i wanted you to add is for a different reason.

So in benefits section the towing, windscreen and some other will be under addons and the rest others will be under foc or free of charge.
Now does it actually got any special logic or anything in the software then the answer is no. it doesnt have such kind of special logics because this will just help the template creator or the person that will create the template to easily go through the benefits and quickly add the Free of charge ones grouped by differnt benefit options as well i said in the left menu. so it will be easy and less confusing during creation.
