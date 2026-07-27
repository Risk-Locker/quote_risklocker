
## Direct questions before I write the new `prompts.md`

1. **Top-level names and URLs**
   - Rename sidebar “Admin” to **“Customize”** and URL `/admin` → `/customize`? 
     personaliztion. it will have mainly role based stuffs, current role or users info 
   - New section also need to created which is settings

- Logs containing all the logs including server , system, users who did what like if they generated record or anything. per user by user info not just one big log page. proper date by date timing so that user dont get confused with the huge bunch of logs everyday the open it or every hour they open it.
- New section called **“Extraction”** at `/extraction`? Should `/upload` redirect there or stay as the entry
  point?
- also new section called Builder which will actually have the current admin tabs stuffs but in a different unique was as stated

2. **Role access**

   - Staff sees **only Extraction**. Admin/dev/super_admin see **both Extraction and Customize**. Correct? yes correct
(dont seperate anything for now. all user roles can do everything apart from some role based actions like kicking someone of the same level. Apart from that all have full access to the builder, extraction everything..) Also in the login portal add a 10 times wrong password block for 1 minutes. and if this happens again the time increases to 5 minutes. if this happens again then next it will be 5 times wrong password then block that ip and mac address for 30 minutes. also add a feature under systems that someone of this ip address and this mac address and device id and this location tried to access this many times. i know in the logs already will show all this but still i want this one to be a seperated. cause normally nobody apart from 10 people max should have access to this. though its in public portal but anyone apart from staff shouldnt access and accessing it will be simmilar to like knowingly tesspassing to a private property. So logging in or trying to crack something is simmilar to going to a honeypot. So thats why this info should be intercepted properly. 

Now normalyl there can be only 1 situation where a hacker tries 1000 times and find the right password thats the only option or else there is no way to access. but even if they access there should be a way to know that who are currently active in the site and can be seen by there under active users. Also nobody can kick anyone apart from the admin or super admin. so even if that hacker logs in the super admin can just go in and remove him. also any other user if login the staff and dev will reive a notidication in the app that this person or that person logged in.

3. **Company list**

   - Final list: **QBE, AmGen, Liberty, STMB, Tune, Etiqa, Lonpac, Sompo**. Correct?
   - Should **AmGen** and **AmAssurance** be treated as one company? wait no Aminsurance. listen this ones you for  now create later user can create more add more edit it even. and by default keep exactly the 6 insurances. 
   QBE
   AmGen
   Liberty
   STMB
   Tune
   Etiqa
   Lonpac
   Sompo
   (this one this are the companies or insurance companies. under this can have multiple templates like aminsurance or others if needed. This are the main inusreance. from it can be 2 or 3 templates) so your goal here is to just keep this 6 as default. also user can change the value of the default ones but cannot delete it completely. they can also stop it or disable it if they want but cant delete this 6 cause the sompo and lonpac is the most rarest ones and most rarely used maybe once in a month or few months but still its not totally disqualified. now its presence is not an issue but for proper future thinking and scalability i think there should be default 6 and user can create more thats all. this 6 names they can change or remove but multiple company names cant be same like 2 amgen cannot exist but amgen 2.0 or amgen 2 still going to be accepted. (even though me and u both know this is repeated but still keep this feature)

   - Is it **Sompo** or **Somp**? Berjay Sompo Insurnace or Sompo in short
4. **Default templates**

   - Should the system **auto-create one locked default template** for each of the 8 companies on startup, or should the admin create them manually? 
   listen no need autocreate 8 companies one. just create 6 default templates one for each :
   QBE
   AmGen
   Liberty
   STMB
   Tune
   Etiqa

   also for a reference of how the template will nearly be or the format is going to be almost exactly this : 

assets\quotation_template_example_global.png


5. **Our Specials data model**

   - Do you want a separate `benefit_variants` table, or flatten it as rows with `parent_benefit_id`? yes. so simply each benefits can have multiple versions
   example : towing simply will have 2 or 3 types of towing versions which are basically going to be svgs with text simply. so the flow is like this . Also dont call it benefits. i mean benefits is okay but call it Our Specials so under this page will have
   multiple variants :
   - windscreen : 
   (1)  Windscreen Coverage (Up to RM 300)
   (2)  Windscreen Coverage (Up to RM 400)		
   (3)  Windscreen Coverage (Up to RM 500)
   (4)	Windscreen Coverage (2 times change in 2 years)	
   - Workmen Ship : 
   (1)  3 Years Workmen Ship Warranty		
   (2)  2 Years Workmen Ship Warranty		
   (3)  1 Years Workmen Ship Warranty		
   - Ambulance Fee : 
   (1)  Ambulance fee upto 1000 RM		
   (2)  Ambulance fee upto 2000 RM	
   (3)  Ambulance fee upto 3000 RM
   (3)  Ambulance servce 2 times during the coverage

   like this there going to be around 15 to 20 specials. and under that will have multiple variants.
   So we can simply say special categories and then splitted into special variants which you called as variant id which is okay.
   	
    so the final thing that will be used is the variant id inorder to add that in the builder profile.
   


   - Is the category exactly two values: **FOC** and **Add-on**? Yes. but thius one is just for show or display. normally it doesnt have strict logical value. Normally it will help during the template builder moment so when the user will start selecting the specials then it will be hard to remember which one should be in special and which ones in addon. so this will help them easily understand. but in case user wants to add the addons in the our specials section or anywhere it really doesnt matter. its just a visual understanding thats all.


6. **Our Specials mini-builder fields**

   - My guess: label, value text, icon asset, category (FOC/Add-on), shape, background color, text color. Anything missing?

i think thats more than enough. also each specials should look something like this :
assets\icons_hive copy - Copy.png
assets\icons_hive copy 2.png
assets\icons_hive copy.png
"
though some images might be wrong here but this is just for your own and reference understanding.

7. **Template builder integration**

   - When a variant is dragged onto the canvas, should it be a **reference** to the variant (so later edits to the variant update all templates), or a **snapshot** normally a variant wont be dragged. think in canva when we click on elements we need to write or search something so lets say we search rectangle then a lot of images appear as well as the groups also appear like 3d, normal, artistic. other custom variants.

   now think here the case is simmilar.
in the left side under specials will have all the variants showing. now lets say user clicked on filter by variants. then only 18 seperate dropdown will show now it could be 18 or 16 depending on how many the admin created before. After that the one the user needs under each variants that will be choosen and placed in the template by drag n drop thats it.

basically its just createing a premade component and reusing it thats all nothing so complicated

8. **Extraction flow**

   - Should the review page move to `/extraction/review/[id]`? yes. think it of just like chatgpt chats thats it. everyday when user open based on that date can see all the sessions they created  (yes this is okay. so after uploading and proceeding will create a new session and in that session no new pdf can be uploaded. that session will be completely based on the first pdf that was uploaded. also it will retain all the previous edits done even if user opens it after 2 weeks. by edits i mean like lets say they cahnge some fields info. some editing the template so all this can be done here)
   - Should the user **confirm/select the insurance company** during extraction, or only auto-detect from filename? aut detect is by default. (if it cannot auto detect then obiously user needs to do the detection.) 



9. **PDF preview session edits**

   - What kind of “tiny edits” should be allowed in the preview? Text/value tweaks, benefit selection, layout nudging, or something else? full edits cause normally nobody will do any edit there but even if they want to do then they can do almost everything like its just a simple builder profile with information. now if they wanna remove variable and mess it up also can but it will not affect or change anything in the main system or main templates or addons or any settings there as those are lengthen only to that specefic session and upload
(this part i will tell you clearly. first wrong thing you are saying is pdf preview where the final output that will be generated can be both an image or a pdf. so it can be both. Now the edit that user will do during the preview mode will be totally simmilar to the edit they do during building. yes they can just literally delete everything download an empty blank page. so that level of editing they can do. 
now there is one small thing i want to mention. incase they edit in the preview mode it will never ever change the template he used or the template that was used. rather after editing if the user wants to save this as a new template then they can simply save it without any issues so it will be shown there in alongside the other templates with a new name as set by the user or the deafult session name.  The reason for this is testing and learning on the run for the staffs. since most users here are non tech so they should be able to do it and also learn it alongside. it gives them freedom and yet skills to later themselves edit the tempaltes instead of needing the developer.  
)
 


10. **Prompts.md styles** 

    - Should I **replace** the old prompts entirely, or keep them as a superseded archive at the bottom?
   What i want is not to delete it. just try to combine both. if that prompt got conflicting rules or features that is not matching the logic of current prompt than in that case you will use this latest prompt and instructions i gave. In case its a new feature and that needs to be in the app or else its gonna be a bad thing then better add it. 
   dont just archive it at the bottom cause this prompts.md will be the final prompt that will make this whole application final and working with everything working. 
   So that the last thing that needs to be developed in the end are simply just deployment to serverm, adding google 0auth or anything else, add more security features etc... so this are the last thing that will be done and you dont need to mention this in the prompts.md the prompts.md will have the prompts needed to have a final full perfect version that is working. no logic falws, no errors in any endpoints, all clicks are working smoothly, no glitches, No non functional half coded features. 
   perfect text extraction, perfect flow, no glitches , runs super fast etc...

    - Should I drop the “Required skills” section, or keep it minimal (max 2–3 skills)? (max 1 to 3 skills and if none needed then none. again dont force unless needed. if you think the model deepseek v4 or glm or qwen or gpt terra or luna or any other model will need skills or else it cant do it then add that specefic skill in that part or else no need to force it please)
      Answer whichever ones you care about. Once you confirm, I will write the new `prompts.md` in small, unit-wise prompts that any model can follow one by one.
      (unit-wise prompts that any model can follow one by one. also make sure each prompts have proper instruction that will make it tick the part or mark the specefic unit it finished doing and its working. now user will also verify themselves and if user finds the unit still not working then yes user will give the prompt again as well but it should say somethin like doen or finished to the side of the prompt title)

