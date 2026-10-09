import csv, re
base=list(csv.DictReader(open("data/candidates/seed_cardiology_ophthalmology.csv",encoding="utf-8")))
H=["practice","specialty","city","address","phone","priority","evidence","source","providers","size_override","review","check","kind"]
rows=[]
CARD_REVIEW={
"New Brunswick Cardiology Group":("High","Is it independent or owned by RWJBarnabas? Look for 'RWJPE' or RWJBarnabas branding. Drop it if system-owned.",6,""),
"Cedarbrook Cardiology":("High","Is the doctor employed by Hackensack Meridian? Check the site for HMH branding.","",""),
"Raritan Bay Cardiology Group PA":("High","Is it unrelated to Hackensack Meridian's Raritan Bay hospital? Confirm owner, offices and phone.","",""),
"Cardio MD":("High","Does a cardiologist actually practice at this address? Call or search the building.","",""),
"HealthExcel Cardiology Associates":("High","Confirm it is a current cardiology practice (Suite J or K?). Get a phone number.","",""),
"Cardiology of New Jersey":("Medium","Independent, or part of a system or platform? Website and claimed Google profile? Phone.","",""),
"CardioMedical and Vein Center":("Medium","Mainly cardiology or vein/cosmetic care? Website, Google profile, review count, phone.","",""),
"Jersey Heart Center LLC":("Medium","Seven physicians across five specialties: who owns it and who handles marketing?",7,""),
"Medical Diagnostic Associates":("Medium","Cardiology practice or multi-specialty diagnostic center? Website, review count. Phone on file.",2,""),
"Heart & Vascular Center of New Brunswick":("Medium","Does it exist as listed? Owner, website, Google profile.","",""),
"Practice Associates Medical Group":("Medium","Is cardiology a main service or one line of a multi-specialty group? Who runs marketing?","",""),
"Primecare Medical Group":("Medium","Larger multi-specialty group hiring cardiologists: find its marketing contact; different pitch (growth).","","Large"),
"Monmouth Cardiology Associates":("Low","Confirm it is still independent; get the website. Offices: Somerset and Monroe (3 providers at Monroe).",3,""),
"Cardio Metabolic Institute":("Low","Confirm independence; get the website and Google profile.","",""),
"Howard Blau, MD":("Medium","Solo, or part of a group? Practice name, website, phone.",1,""),
"Nihir Shah, MD":("Medium","Independent office or hospital-owned practice? Practice name, website.",1,""),
"Henry Altszuler, MD":("Medium","Still practicing? Two offices (South Plainfield, Metuchen). Practice name and website.",1,""),
}
OPH_FLAGS={"Health Check Medical And Eye Center":"High","Ophthalmic Consultants of Somerset":"High","Garden State Ophthalmology":"High","Watchung Eye Care LLC":"Medium",
 "The Eye Care & Surgery Center":"Low","James Chelnis, MD":"Low"}
OPH_SIZE={"Specialty MD Inc":2,"Princeton Eye Group - Monroe":3,"Watchung Eye Care LLC":3,"The Eye Center (Warren)":2,"Shamim Eye Care":2}
GEN="Confirm the practice is open and who owns it (solo, group, DSO or system); website quality; Google profile claimed? and review count; phone."
for r in base:
    n=r["practice"]; rr=dict(r)
    ind=bool(re.search(r",\s*(MD|DO)\b",n)) or n in {"Joseph Napolitano, MD"}
    rr["kind"]="individual" if ind else "practice"
    if r["specialty"]=="Cardiovascular Disease":
        rev,chk,prov,ov=CARD_REVIEW.get(n,("Medium",GEN,"",""))
    else:
        rev=OPH_FLAGS.get(n,"Low" if r["priority"]=="1" else "Medium"); chk=GEN; prov=OPH_SIZE.get(n,1 if ind else ""); ov="Large" if n=="The Eye Care & Surgery Center" else ""
    rr.update(providers=prov,size_override=ov,review=rev,check=chk); rows.append(rr)

def add(spec,items):
    for it in items:
        name,city,addr,phone,pri,evid,src,prov,ov,rev,chk,kind=(list(it)+[""]*12)[:12]
        rows.append(dict(practice=name,specialty=spec,city=city,address=addr,phone=phone,priority=pri or 2,evidence=evid,source=src or "Directory listing (web search)",
                         providers=prov,size_override=ov,review=rev or "Medium",check=chk or GEN,kind=kind or "practice"))
PT="Physical Therapist"
add(PT,[
("FOX Rehabilitation","Edison","","",1,"Recruiting post: clinician-owned and operated private practice (geriatric rehab); may be a large multi-office group","Job posting","","","Medium","Confirm the Edison office and its size; if it has many clinicians set Size Override to Large."),
("Procare Physical Therapy P.A.","Piscataway","4500 New Brunswick Ave, Suite 101","(732) 926-9250",2,"PA with offices in Piscataway and South Plainfield (562 Arlington Ave)","Healthline"),
("Mana Physical Therapy","East Brunswick","","",2,"PT, manual and pelvic floor therapy","Directory listing"),
("Rehabilitation Services Associates LLC","East Brunswick","3 Tremblay Rd","(732) 254-0772",2,"NPI record last updated 2012: may be closed","NPI listing","","","High","Still operating? Check the phone and a current website."),
("New Brunswick Physical Therapy","New Brunswick","330 Livingston Ave","",2,"WebMD: not accepting new patients, no Medicare/Medicaid (may be outdated)","WebMD","","","High","Is it open and accepting patients?"),
("Central Jersey Physical Therapy Associates","Old Bridge","499 Marlboro Rd","",2,"WebMD: not accepting new patients (may be outdated)","WebMD","","","High","Is it open and accepting patients?"),
("JAG Physical Therapy","Old Bridge","1980 Route 9, Suite 250","",3,"NJ PT company with clinics in North Brunswick, Old Bridge (two) and Whiting","NJBiz","","","Medium","Multi-location company: count its clinics; set Size Override if large."),
("Strive Physical Therapy of Monroe","Monroe Township","1 Rossmoor Dr, Suite 101","",3,"Part of an 18-location network; formerly Forsgate Physical Therapy","Monroe Township news","","Large","Low","Large network: filter out unless you want chains."),
("FYZICAL Monroe Township","Monroe Township","","",3,"FYZICAL franchise network; local owner may decide marketing","Practice site","","","Medium","Who is the local franchise owner?"),
("FYZICAL Green Brook","Green Brook","","",3,"FYZICAL franchise; serves Dunellen","Practice site","","","Medium","Who is the local franchise owner?"),
("Professional Physical Therapy (Edison)","Edison","2035 State Route 27","",3,"Multi-office network (also South Plainfield, Somerset, Bernardsville); acquired Somerset Family PT in 2022","Practice site; press release","","Large","Low","Large network: filter out unless you want chains."),
("Ivy Rehab Physical Therapy (Piscataway)","Piscataway","1630 Stelton Rd","",3,"Network of 130+ NJ locations per its release","Ivy Rehab release","","Large","Low","Large network: filter out unless you want chains."),
("Ivy Rehab Physical Therapy (Somerset)","Somerset","441 Elizabeth Ave","",3,"Network of 130+ NJ locations per its release","Ivy Rehab release","","Large","Low","Large network: filter out unless you want chains."),
("Physis Physical Therapy","Basking Ridge","665 Martinsville Rd, Suite 219","",2,"Standalone name","Directory listing"),
("ABC Physical Therapy","Somerville","50 S Bridge St","",2,"Standalone name","Directory listing"),
("Functional Health Physical Therapy","Somerville","1 Eastern Ave","",2,"Standalone name","Directory listing"),
("Excellent Physical Therapy","Bedminster","","",2,"Listed on a hospital outpatient map; no address captured","RWJ outpatient map","","","High","Does it exist? Find an address and phone."),
("The Sports Rehab and Balance Center","Bedminster","","",2,"Listed on a hospital outpatient map; no address captured","RWJ outpatient map","","","High","Does it exist? Find an address and phone."),
("Comprehensive Orthopedic Physical Therapy","Somerset","900 Easton Ave","",2,"Standalone name","APTA job profile"),
("Trinity Rehab","Somerset","84 Veronica Ave","",2,"Standalone name","Directory listing"),
("Spine & Orthopaedic Physical Therapy Center","Raritan","1130 Route 202 South","",2,"Frank Previte, PT practices here","Directory listing"),
("Kid PT","Raritan","575 NJ-28, Bldg 1, Suite 204A","",2,"Pediatric developmental and neurological therapy","Directory listing"),
("Riverwalk Physical Therapy","Bernardsville","20 Claremont Rd","",2,"Takes most insurance including Medicare","Google business listing"),
("Professional Orthopedic and Sports Physical Therapy of NJ","Bernardsville","150 Morristown Rd, Suite 110","",3,"Registered practice address; may be part of the Professional PT network","NPI listing","","","High","Same company as Professional Physical Therapy? If so set Size Override to Large."),
("Kessler Rehabilitation Center - Somerset","Somerset","120 Cedar Grove Ln","",3,"Directory listing; likely part of a larger rehab network","Directory listing","","","Low","Likely a large network: confirm ownership, then filter out."),
("Kessler Rehabilitation Center - Bernardsville","Bernardsville","37 Old Colony Rd","",3,"Directory listing; its category label looks wrong; likely part of a larger rehab network","Directory listing","","","Low","Likely a large network: confirm ownership, then filter out."),
("Performance Ortho","Branchburg","3150 US-22","",3,"Listed with hours; unclear whether a PT or orthopedic practice","Directory listing","","","High","Is it a PT practice at all?"),
("Ifeanyi Anaemejeh, PT","East Brunswick","317 Rues Ln","",1,"One-on-one private practice; orthopedic and chronic pain","Zocdoc","1","","Medium","Practice name, website, phone.","individual"),
("R. Marion, PT, DPT","Sayreville","","",2,"Outpatient and house calls in Middlesex County (Parlin)","Directory listing","1","","Medium","Practice name, website, phone.","individual"),
("Jerome Ortega, DPT","Bound Brook","","(732) 805-9005",2,"Individual listing","Directory listing","1","","Medium","Practice name, website.","individual"),
])
D="Dentist"
add(D,[
("Daniel O'Brien DMD LLC","Edison","1163 Inman Ave, Suite 103","",2,"General practice LLC (ADA directory)","ADA Find a Dentist"),
("Tina Panchal DMD LLC","Edison","817 Inman Ave","",2,"General practice LLC (ADA directory)","ADA Find a Dentist"),
("Dennis Hopkins Jr., DDS PA","Edison","3830 Park Ave, Suite 203","",2,"General practice PA (ADA directory)","ADA Find a Dentist"),
("KK Dental","Edison","495 Plainfield Ave","",2,"ADA directory listing","ADA Find a Dentist"),
("Philip Shin DDS INC","Metuchen","2 Bridge St","",2,"General practice (ADA directory)","ADA Find a Dentist"),
("Bridgepointe Dental Studio","Metuchen","230 Bridge St","",2,"Spanish spoken (ADA directory)","ADA Find a Dentist"),
("Legacy Dental","Metuchen","38 Bridge St, Bldg A","",2,"ADA directory listing","ADA Find a Dentist"),
("Metuchen Group Dental LLC","Metuchen","26 Bridge St","",3,"Name suggests a multi-dentist group","ADA Find a Dentist","","","Medium","Count the dentists; set Providers."),
("The Dentists of Woodbridge","Woodbridge","424 Amboy Ave, Suite 1","",3,"Two dentists listed: multi-doctor group","ADA Find a Dentist","","","Medium","Count the dentists; set Providers."),
("Eastern Dental of Woodbridge LLC","Avenel","1030 Saint Georges Ave","",3,"Name may indicate a larger chain","ADA Find a Dentist","","Large","Low","Likely a chain: confirm, then filter out."),
("North Brunswick Family Dental & Orthodontics","North Brunswick","825 Georges Rd, Suite 5","",2,"Also offers orthodontics","ADA Find a Dentist"),
("Family Dentistry (Dr. Jyoti Shah)","North Brunswick","646 Hermann Rd","",2,"ADA directory listing","ADA Find a Dentist"),
("Family & Cosmetic Dentistry","North Brunswick","2050 State Route 27, Suite 207","",2,"ADA directory listing","ADA Find a Dentist"),
("East Brunswick Family & Implant Dentistry","East Brunswick","561 Cranbury Rd, Suite K","",2,"ADA directory listing","ADA Find a Dentist"),
("Central Jersey Pediatric Dentistry & Orthodontics","East Brunswick","","",2,"Main office in East Brunswick; serves Old Bridge, Sayreville, Monroe","Practice listing"),
("Mario S. Fiorentini DMD PA","Highland Park","85 Woodbridge Ave","",2,"General practice PA","ADA Find a Dentist"),
("Bloom and Bloom, The Center for Excellence in Dentistry","New Brunswick","815 Livingston Ave","",2,"ADA directory listing","ADA Find a Dentist"),
("Atlantic Dental Healthcare PA","Old Bridge","28 Throckmorton Ln, Suite 201","",2,"PA","Directory listing"),
("Eastern Dental of Old Bridge","Old Bridge","960 US Highway 9","",3,"WebMD: not accepting new patients; likely a chain","WebMD","","Large","Low","Likely a chain: confirm, then filter out."),
("Alpha Omega Dental Care","Monroe Township","219 Half Acre Rd","",2,"Directory listing","Directory listing"),
("Monroe Dental Group LLC","Monroe Township","18 Centre Dr, Suite 102","",3,"Group name: possibly several dentists","Directory listing","","","Medium","Count the dentists; set Providers."),
("SiRa Dentistry","Spotswood","456 Main St","",2,"Opened new offices in early 2024","Dentistry Today"),
("South Plainfield Dental Arts LLP","South Plainfield","1550 Park Ave, Suite 204","",2,"LLP led by Dr. Pietrofesa","ADA Find a Dentist"),
("Park Avenue Dental","South Plainfield","160 Oak Tree Ave","",2,"Languages: Gujarati, Hindi, Italian, Spanish","ADA Find a Dentist"),
("Smiles Dental","South Plainfield","3600 Park Ave, Suite N","",2,"Led by Dr. Ami Patel","ADA Find a Dentist"),
("NuvSmile","Piscataway","1315 Stelton Rd","",2,"ADA directory listing","ADA Find a Dentist"),
("Central Jersey Dental Arts","Piscataway","1056 Stelton Rd, Suite A","",2,"ADA directory listing","ADA Find a Dentist"),
("Aberdeen Family Dental","Piscataway","1312 Centennial Ave","",2,"ADA directory listing","ADA Find a Dentist"),
("Dental Care Bridgewater","Bridgewater","475 N Bridge St","",2,"ADA directory listing","ADA Find a Dentist"),
("Bridgewater Family Dental","Bridgewater","676 US-202/206","",2,"ADA directory listing","ADA Find a Dentist"),
("Bridgewater Dental Group","Bridgewater","216 Finderne Ave","",3,"Group name: possibly several dentists","ADA Find a Dentist","","","Medium","Count the dentists; set Providers."),
("Bright Smile Bridgewater","Bridgewater","215 Union Ave, Suite D","",2,"ADA directory listing","ADA Find a Dentist"),
("For You Dentistry","Bridgewater","477 Union Ave","",2,"ADA directory listing","ADA Find a Dentist"),
("The Children's Dental Center","Somerville","148 W End Ave","",2,"Pediatric dentistry","ADA Find a Dentist"),
("Cornick Family Periodontics","Somerville","210 E Main St","",2,"Periodontics","ADA Find a Dentist"),
("RS Saachi Corp","Somerville","374 E Main St","",2,"General dentist","ADA Find a Dentist"),
("Gentle Dental of Branchburg","Branchburg","3461 US Highway 22","",3,"Gentle Dental is a multi-office dental group","ADA Find a Dentist","","Large","Low","Likely a chain/DSO: confirm, then filter out."),
("Branchburg Pediatric Dentistry","Branchburg","3322 US Highway 22, Suite 201","",2,"Pediatric dentistry","ADA Find a Dentist"),
("Dubitsky Family Dental","Hillsborough","201 Omni Dr","",2,"ADA directory listing","ADA Find a Dentist"),
("Hillsborough Dental Center","Hillsborough","107 Omni Dr","",2,"ADA directory listing","ADA Find a Dentist"),
("Hillsborough Dentistry","Hillsborough","760 US Highway 206, Suite 2","",2,"ADA directory listing","ADA Find a Dentist"),
("TRU Periodontics & Dental Implants","Hillsborough","912 Courtyard Dr","",2,"Periodontics and implants","ADA Find a Dentist"),
("The Star Dental Group","Warren","161 Washington Valley Rd, Suite 202","",3,"Group name: possibly several dentists","ADA Find a Dentist","","","Medium","Count the dentists; set Providers."),
("Soft Care Dental Group","Warren","31V Mountain Blvd","",3,"Group name: possibly several dentists","ADA Find a Dentist","","","Medium","Count the dentists; set Providers."),
("Warren Dental Design","Warren","","",2,"No address captured","ADA Find a Dentist","","","High","Find an address and phone."),
("Ridge Family Dentistry","Basking Ridge","44 S Finley Ave, Unit A","",2,"ADA directory listing","ADA Find a Dentist"),
("Brook Dental Associates","Bound Brook","373 Vosseller Ave","",2,"ADA directory listing","ADA Find a Dentist"),
("Comprehensive Pediatric Dentistry","Bound Brook","111 E Union Ave","",2,"Pediatric dentistry","ADA Find a Dentist"),
("Mondovi Dental","Raritan","64 E Somerset St","",2,"Dr. Douglas Masi also listed at this address","ADA Find a Dentist"),
("KK Dental Associates - Somerset","Somerset","1743 NJ-27","(732) 402-6207",2,"Directory listing","Directory listing"),
("Somerset Smiles","Somerset","650 Easton Ave","(732) 249-5500",2,"Directory listing","Directory listing"),
("Somerset Dental PC","Somerset","1707 Route 27 South","",2,"Directory listing","Directory listing"),
("Somerset Family Dentistry","Somerset","11 Clyde Rd, Suite 101","",2,"Directory listing","Directory listing"),
# individuals
("Hiren H. Shah, DMD","Edison","34-36 Progress St, Suite B6","",3,"Individual general dentist listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("John J. Keating, DMD","Edison","3826 Park Ave, Suite 100","",3,"Individual general dentist listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("William Margolin, DMD","North Brunswick","746 Livingston Ave","",3,"Individual; Zocdoc: accepts Aetna, Cigna, Delta Dental","Zocdoc","1","","Medium","Practice name, website, phone.","individual"),
("Ami Shah, DMD","East Brunswick","647 NJ-18, Suite A","",3,"Individual; Zocdoc listing","Zocdoc","1","","Medium","Practice name, website, phone.","individual"),
("Riki T. Kreitman, DMD","Highland Park","34 S 4th Ave","",3,"Individual; Hebrew spoken","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("Tara Savage, DDS","Old Bridge","","",3,"Individual; accepting new patients","Directory listing","1","","Medium","Practice name, website, phone.","individual"),
("Dipti Modi, DDS","South Amboy","","(732) 727-0474",3,"Individual; 4.7 stars","Directory listing","1","","Medium","Practice name, website.","individual"),
("Lydia David, DDS","Perth Amboy","325 State St","",3,"Individual; Spanish spoken","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("Joseph Micale, DMD","Basking Ridge","12 Ridge St","",3,"Individual general dentist listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("Zora Stefanovski, DMD","Bound Brook","106 E Union Ave","",3,"Individual listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("Nicole Padovan-Lagrasta, DMD","Bound Brook","105 E Union Ave","",3,"Individual listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
("Richard A. D'Avanzo, DMD","Raritan","901 US Highway 202","",3,"Individual listing","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
])
# ---- part 2: sub-specialties, new dentist specialties, mental health, size marking ----
for r in rows:
    r["segment"]={"Cardiovascular Disease":"cardiology","Ophthalmology":"ophthalmology","Physical Therapist":"pt","Dentist":"dentist"}[r["specialty"]]
    r["subspecialty"]={"Cardiovascular Disease":"Cardiology","Ophthalmology":"Ophthalmology","Physical Therapist":"Physical therapy","Dentist":"General dentistry"}[r["specialty"]]
    r["size_basis"]=""
SUB={"Central Jersey Pediatric Dentistry & Orthodontics":"Pediatric dentistry","The Children's Dental Center":"Pediatric dentistry","Branchburg Pediatric Dentistry":"Pediatric dentistry",
     "Comprehensive Pediatric Dentistry":"Pediatric dentistry","Cornick Family Periodontics":"Periodontics","TRU Periodontics & Dental Implants":"Periodontics",
     "Bloom and Bloom, The Center for Excellence in Dentistry":"General dentistry"}
for r in rows:
    if r["segment"]=="dentist" and r["practice"] in SUB: r["subspecialty"]=SUB[r["practice"]]

def add2(segment,sub,items,spec=None):
    for it in items:
        name,city,addr,phone,pri,evid,src,prov,ov,rev,chk,kind,basis=(list(it)+[""]*13)[:13]
        rows.append(dict(practice=name,specialty=spec or sub,subspecialty=sub,segment=segment,city=city,address=addr,phone=phone,priority=pri or 2,evidence=evid,
                         source=src or "Directory listing (web search)",providers=prov,size_override=ov,review=rev or "Medium",check=chk or GEN,kind=kind or "practice",size_basis=basis))
DS="Directory listing (web search)"
# -------- dentists by specialty
add2("dentist","Pediatric dentistry",[
("Dentistry for Kids","Edison","4 Progress St, Suite B1","",2,"March 2026 press release: expanded children's services; sedation, special needs care","Press release"),
("KidZdent","Old Bridge","","(732) 679-2323",2,"NJ Dental Association Special Olympics provider list","NJDA provider list"),
("Kids Smile","Monmouth Junction","","(732) 297-5200",2,"Pediatric dentistry listing","NJDA provider list"),
("Tendersmiles4kids","North Brunswick","","(732) 249-1010",2,"Listing; a related 'Tender Smiles 4 Kids of Edison' also appears","NJDA provider list","","Medium","Medium","Multiple offices? Count them.","","Suspected: separate Edison and North Brunswick listings"),
("Tender Smiles 4 Kids of Edison","Edison","","(732) 549-3773",2,"From a 2015 directory: confirm it still operates","2015 directory","","","High","Still open? Same owner as Tendersmiles4kids?"),
("Children's Dental Specialists & Adult Dentistry","Warren","","",2,"Job post says it has served Warren and Chester since 2006; recruiting a pediatric dentist","Job posting"),
])
add2("dentist","Orthodontics",[
("All Star Family Orthodontics","Old Bridge","3331 Highway 9 North","",2,"Dr. Jason Vives; traditional braces and Invisalign","Directory + practice page"),
("Chan Orthodontics","East Brunswick","385 Cranbury Rd, Suite 5","",2,"Directory listing","wellness.com"),
("Orthodontic Associates","Piscataway","121 Metlars Ln","",2,"Also has a New Brunswick office","wellness.com","","","Medium","Multi-office: count orthodontists."),
("Bridge Pointe Orthodontics","Metuchen","203 Bridge St, Bldg D","",2,"Dr. Jenny Rong, DDS MS PC","wellness.com"),
("Orthodontics Specialist PC","Metuchen","456 Middlesex Ave","",2,"Directory listing","wellness.com"),
("Progressive Orthodontics","New Brunswick","1303 State Highway 27","",2,"Directory listing","wellness.com"),
("Somerset Orthodontic Specialists","Somerville","199 W High St","",2,"WebMD: not accepting new patients (may be outdated)","WebMD","","","High","Open and accepting patients?"),
("Eastern Orthodontic Associates","Sayreville","","",3,"Name echoes the Eastern Dental chain; verify","wellness.com","","Large","Low","Same company as Eastern Dental? If so filter out.","","Suspected: name matches Eastern Dental"),
("Allan Braunstein, DMD","Edison","1941 Oak Tree Rd","",3,"Individual orthodontist listing","wellness.com","1","","Medium","Practice name, website, phone.","individual"),
("Emily Yu, DMD, MSD","Piscataway","5 Wills Way","",3,"Individual orthodontist listing","wellness.com","1","","Medium","Practice name, website, phone.","individual"),
("Sanford Bosin, DMD","Old Bridge","2101 Route 516, Suite A","",3,"Individual listing","wellness.com","1","","Medium","Practice name, website, phone.","individual"),
("Glenn D. Goldstein, DMD","Somerset","Route 27","",3,"Board certified orthodontist (AAO); also a Randolph office","AAO locator","1","","Medium","Practice name, website, phone.","individual"),
("Robert Silverstein, DMD","Somerset","Worlds Fair Dr","",3,"Orthodontist; 5.0 rating from one review","AAO / Healthline","1","","Medium","Practice name, website, phone.","individual"),
("Monika Chan, DMD, MScD","Somerset","Route 27","",3,"Board certified orthodontist; also Martinsville and North Brunswick offices","AAO locator","1","","Medium","Practice name, website, phone.","individual"),
("Robert Peterman, DMD","Somerville","","",3,"Orthodontist listing","Healthline","1","","Medium","Practice name, website, phone.","individual"),
])
add2("dentist","Periodontics",[
("Edison Periodontics and Implantology","Edison","98 James St","",2,"Group practice, 3 physicians listed; implants and bone grafting","WebMD","3"),
("Middlesex Periodontics & Dental Implants, PC","East Brunswick","A3 Cornwall Dr","(732) 257-7300",2,"Directory data verified by phone about six years ago","Data Axle listing","","","High","Still open? Directory data is old."),
("East Brunswick Periodontics and Dental Implants","East Brunswick","7 Brier Hill Ct","",2,"Two physicians listed; WebMD says not accepting new patients","WebMD","2","","High","Open and accepting patients?"),
("Nathan C. Steele, DMD, PC","Bridgewater","17 Monroe St","",2,"Periodontics; WebMD says not accepting new patients","WebMD","","","High","Open and accepting patients?"),
("Associated Periodontists, LLC","Warren","65 Mountain Blvd Ext, Suite 101","",2,"Dr. Tracy Ginsburg","ADA Find a Dentist"),
("Nina Lehrhaupt, DMD","Edison","34 Progress St","",3,"Solo practice per directory; dental implants","New Patients Inc","1","","Medium","Practice name, website, phone.","individual"),
("Tat Chiang, DMD","Somerville","10 N Gaston Ave","",3,"Periodontics; LANAP laser therapy","New Patients Inc","1","","Medium","Practice name, website, phone.","individual"),
("Scott Zirkin, DMD","Bridgewater","216 Finderne Ave, Suite 5","",3,"Periodontist at Bridgewater Dental Group","Vitals","1","","Medium","Part of Bridgewater Dental Group?","individual"),
("Laura D. Swerdlin, DMD","Somerset","1527 State Route 27, Suite 2200","",3,"Periodontics","ADA Find a Dentist","1","","Medium","Practice name, website, phone.","individual"),
])
add2("dentist","Endodontics",[
("Mid Jersey Endodontic Group","Somerville","57 W End Ave","",2,"Two endodontists listed; also an Old Bridge office; WebMD says not accepting new patients, Vitals says accepting","ADA / WebMD / Vitals","2","","Medium","Multi-office group: count endodontists; confirm open."),
("Advanced Endodontic Associates","Old Bridge","","",3,"NJ Monthly recognition (Apolito, Zohn); town not stated: confirm office","NJ Monthly","2","","High","Which towns? Is there a Middlesex or Somerset office?"),
("Endodontist at 35 Throckmorton Ln (name unconfirmed)","Old Bridge","35 Throckmorton Ln","",3,"AAE directory lists an endodontist here with other offices in New Brunswick","AAE directory","","","High","Find the practice name and owner."),
("Brad Strober, DMD (Gentle Dental Care)","Edison","2060 Oak Tree Rd","",3,"Listed as an endodontist at Gentle Dental Care","Healthline","","Large","Low","Gentle Dental is a chain: confirm, then filter out.","","Suspected: Gentle Dental is a multi-office group"),
("Martin Marks, DMD","Piscataway","1100 Centennial Ave, Suite 101","",3,"Endodontist listing; practice name not shown","Healthline","1","","High","Confirm practice name and that he still practices here.","individual"),
("Stacey Goldstein, DMD","Bridgewater","676 US Route 202/206 N","",3,"Endodontist at Bridgewater Family Dental per a local directory","Macaroni Kid","1","","Medium","Part of Bridgewater Family Dental?","individual"),
])
add2("dentist","Oral and maxillofacial surgery",[
("Edison Clark Oral Surgery Associates","Edison","1857 Oak Tree Rd","",2,"WebMD conflicting on new-patient status","WebMD","","","Medium","Open? Number of surgeons?"),
("Oral Surgery Group","East Brunswick","172 Summerhill Rd, Suite 3","",2,"One physician listed (David Rauch)","WebMD"),
("Central Jersey Oral and Maxillofacial Surgery","Old Bridge","2101 Highway 516, Suite C","",2,"Accepting new patients; Medicaid yes, Medicare no","WebMD"),
("Raritan Bay Oral and Maxillofacial Surgery","Woodbridge","676 Amboy Ave","(732) 442-1860",2,"WebMD shows a mixed group of providers","WebMD","","","Medium","Who are the surgeons? Related to the Raritan Bay hospital brand?"),
("Somerset Oral & Maxillofacial Surgery","Hillsborough","390 Amwell Rd","",2,"Founded 1970; offices in Hillsborough and Somerville (85 W High St); recruiting a surgeon (June 2026)","WebMD / job posting","3","","Medium","Count surgeons; website www.somersetoms.com."),
("Aesthetic Oral and Maxillofacial","Somerville","348 E Main St","",2,"Dr. Burt Abramson","WebMD"),
("Warren Oral Surgery and Dental Implant Center","Warren","58 Mt Bethel Rd, Suite 301","",2,"Directory listing","wellness.com"),
])
add2("dentist","Prosthodontics and implants",[
("Prosthodontic Associates of New Jersey","Edison","98 James St, Suite 303","",2,"4.9 average rating; takes Aetna, UnitedHealthcare and others","Practice finder"),
("Central NJ Prosthodontics","East Brunswick","","",2,"Dr. Nainesh Desai; implants, All-on-4, veneers; also an East Windsor office","Practice site"),
("Edison Prosthodontics","Edison","1941 Oak Tree Rd, Suite 301","",3,"Doctor also has a Hackensack Meridian profile","HMH provider page","","","Medium","Employed by HMH or independent?"),
("Nicholas Jacobs, DMD","Woodbridge","90 Woodbridge Center Dr, Suite 300","",3,"Prosthodontist; other office in Roseland","Healthline","1","","Medium","Practice name, website, phone.","individual"),
("David A. Lipani, DMD","Bridgewater","720 US Highway 202/206","",3,"Prosthodontics practice","Directory listing","1","","Medium","Practice name, website, phone.","individual"),
])
add2("dentist","General dentistry",[
("Edison Dentistry PC","Edison","1719A Lincoln Highway","",2,"General practice that places implants and does cosmetic work","New Patients Inc"),
("East Brunswick Family and Cosmetic Dental Group","East Brunswick","","",3,"Group practice per WebMD","WebMD","","","Medium","Count the dentists; set Providers."),
("AC Dental","East Brunswick","300 Route 18","",3,"General practice with an on-site oral surgeon","Directory listing","","Medium","Medium","Count the dentists; set Providers.","","Suspected: multi-provider office with an on-site surgeon"),
("Aspen Dental (East Brunswick)","East Brunswick","269 State Route 18 S, Suite B","",3,"Aspen Dental is a national dental support organization","Aspen Dental site","","Large","Low","National chain: filter out.","","Evidence: national chain (company site)"),
("Aspen Dental (Iselin)","Iselin","799 US Highway 1","",3,"Aspen Dental is a national dental support organization","Aspen Dental site","","Large","Low","National chain: filter out.","","Evidence: national chain (company site)"),
("Amit Vora, DDS","Edison","","",3,"Individual general dentist listing","New Patients Inc","1","","Medium","Practice name, website, phone.","individual"),
])
# -------- mental health
MH="Mental health"
add2("mental_health","Group practices and clinics",[
("Integrative Therapy Institute of NJ","Metuchen","","(732) 517-7658",2,"Group practice in clinical and counseling psychology at several NJ locations (Metuchen, Skillman)","Psychology Today","","Large","Medium","Count therapists across offices.","","Suspected: several locations, many therapists"),
("Institute for Personal Growth (IPG Counseling)","Highland Park","1119 Raritan Ave","",2,"Psychologists and LCSWs; offices in Highland Park, Jersey City and Freehold","Practice site","","Medium","Medium","Count clinicians.","","Suspected: three offices, mixed staff"),
("LifeStance Health (North Brunswick and other NJ offices)","North Brunswick","343 Old Georges Rd","",3,"National chain; says it has 19 NJ offices; clinicians also listed for Piscataway, Plainsboro, South Plainfield, Perth Amboy, East Brunswick","LifeStance site","","Large","Low","National chain: filter out.","","Evidence: company site says 19 NJ offices"),
("Lifebulb (Edison)","Edison","","",2,"Team of licensed professionals; virtual options","Lifebulb site","","Medium","Medium","Count clinicians; other offices?","","Suspected: team practice"),
("The Howard Center for Wellness","Iselin","","",2,"Youth and adult counseling; statewide virtual","TherapyDen","","","Medium","Owner and clinician count."),
("Blueprint Mental Health","Somerville","","",2,"Children, teens and adults; in person in Somerville, virtual statewide","Psychology Today"),
("Clear Conscience Counseling LLC","South Plainfield","2509 Park Ave","",2,"Mental health and substance abuse counseling; EMDR; IOP","CopeCompass"),
("One Step at a Time Therapy Center","East Brunswick","","(732) 210-2444",2,"In-home and office sessions across Middlesex County; private insurance and self-pay","Middlesex ResourceNet"),
("Center for Cognitive Behavior Therapy","East Brunswick","","",2,"CBT and DBT for children, adolescents and families","TherapyRoute"),
("Center for Therapy & Counseling Services","East Brunswick","","",3,"Sliding scale; social work interns involved; may be a training or nonprofit clinic","FSU placement listing","","","Medium","For-profit practice, nonprofit, or training clinic?"),
("Thrive Counseling Center","Old Bridge","","",2,"Teens and young adults; telehealth for NJ and NY","Middlesex ResourceNet"),
("Positive Reset of Warren","Warren","","",2,"Treatment center: therapy, group counseling, medication management","Psychology Today","","","Medium","Clinic scale and owner."),
("Central Jersey Comprehensive Treatment Center","Piscataway","","",3,"Medication-assisted treatment program (08854 listing); likely part of a larger treatment company","Theravive","","Large","Medium","Part of a chain? If so filter out.","","Suspected: treatment-program name used by multi-site operators"),
("Coordinated Family Care of Middlesex County","North Brunswick","","732-572-3663",3,"CARF-listed children and adolescents program; may be a nonprofit agency","CARF directory","","","Medium","Nonprofit agency or practice? Different buyer. Note: the engine's public-sector filter drops it from the lead list because the name contains 'County'."),
],spec="Mental health")
add2("mental_health","Individual clinicians",[
("Sharon R. Evancio, MA, LPC","Metuchen","","",3,"Private practice: individual, couples, family counseling","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
("Nancy Howard, MSW, LCSW","Edison","","",3,"In person and teletherapy; CBT and DBT","Theravive","1","","Medium","Practice name, website, phone.","individual"),
("Samantha Jones, PsyD","Iselin","","",3,"Clinical neuropsychologist: assessment of memory loss, TBI, ADHD","Directory listing","1","","Medium","Practice name, website, phone.","individual"),
("Nicole York, MA, LAC","Iselin","","",3,"Online-only counseling","Psychology Today","1","","Low","Online-only: local search matters less.","individual"),
("Suzi Millar, PsyD","Bridgewater","","",3,"Online-only therapy including Arabic","Psychology Today","1","","Low","Online-only: local search matters less.","individual"),
("Rebecca Hartman, PsyD","Somerville","","",3,"Psychologist for children and teens; not accepting new clients","Psychology Today","1","","High","Closed to new clients: drop unless she expands.","individual"),
("Marion Rollings, PhD","Hillsborough","101 New Amwell Rd","908-500-7295",3,"Licensed psychologist; also serves Bridgewater","Theravive","1","","Medium","Practice name, website.","individual"),
("Jennifer Wacker, MA, EdM, LPC","Bridgewater","","",3,"Licensed professional counselor: depression, anxiety, postpartum, adoption","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
("Alex Soloway, MD","Bridgewater","","",3,"Double board-certified psychiatrist, child and adolescent","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
],spec="Mental health")
# -------- mental health: deeper pass (group practices with several clinicians)
OWN="Is it owned by a hospital system or a private-equity platform, or is it clinician-owned?"
add2("mental_health","Group practices and clinics",[
("Bridge to Balance","Piscataway","","",1,"Counseling center: 3 locations, over 30 clinicians; children from age 5, teens, adults, seniors","Middlesex ResourceNet","30","","High","Confirm the Piscataway office, owner and who handles marketing. At 30+ clinicians this is Large: check the Size filter before outreach.","","Evidence: directory says over 30 clinicians"),
("Center for Marriage and Family Therapy","Piscataway","","",1,"Network with offices in Matawan, Freehold, Princeton, Toms River and Piscataway; LPCs and LCSWs","Directory listing","","Medium","High","Count clinicians and offices; who owns and markets it?","","Suspected: five offices, several therapists each"),
("Ellie Mental Health (Old Bridge / Piscataway / South Brunswick)","Old Bridge","","",2,"Hiring LPCs/LCSWs for Old Bridge, Piscataway and South Brunswick; full-time and contractor roles","Ellie careers page","","Medium","Medium","Franchise: each clinic is locally owned. Find the local franchise owner and count therapists per site.","","Suspected: franchise brand with three NJ sites hiring"),
("Multi-Cultural Counseling Center","North Brunswick","","",2,"Listed on Psychology Today as a multi-clinician resource","Psychology Today","","Medium","Medium","Count clinicians; owner; website quality.","","Suspected: multi-clinician listing"),
("Rossi Psychological Group","Somerville","62 E Main St","",2,"Single-location psychology group","WebMD","","","Medium","Count psychologists; website and Google profile."),
("CogniCare Psychological Services","Branchburg","","",2,"Psychological services; an LPC listed","Psychology Today","","","Medium","Count clinicians; website and Google profile."),
("Hackensack Meridian Bay Behavioral Health","Old Bridge","Old Bridge Medical Arts Building, 3rd floor","732-360-4077",3,"Outpatient psychotherapy, psychiatric evaluation and medication monitoring","HMH site","","Large","Low","Health-system owned: filter out.","","Evidence: Hackensack Meridian Health site"),
("Thriveworks (Edison)","Edison","","",3,"National counseling and psychiatry chain","Thriveworks site","","Large","Low","National chain: filter out.","","Evidence: national company"),
],spec="Mental health")
add2("mental_health","Psychiatry practices",[
("Neuro Bloom Behavioral Health","Iselin","","",2,"Mental health nurse practitioner offering talk therapy and medication management","Psychology Today","","","Medium","Group, or one NP?"),
("OCA Behavioral Health Services","Old Bridge","","",2,"Psychiatric evaluation, treatment plans and medication management; a nurse practitioner's practice","Psychology Today","1","","Medium","Solo NP or a group? Website and Google profile."),
("Lifebulb Psychiatry (Edison)","Edison","","",2,"In-network psychiatry at the Edison office or online; dedicated billing team","Lifebulb site","","Medium","Medium","Same company as the Lifebulb counseling row; count psychiatrists and prescribers.","","Suspected: multi-prescriber team"),
("Ramandeep Kaur, MD","Edison","","",3,"Dual board-certified adult and child-adolescent psychiatrist","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
("Sheema Imran, MD","Old Bridge","","",3,"Psychiatrist","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
],spec="Mental health")
add2("mental_health","Testing and child psychology",[
("Center for CBT: neuropsychological evaluation (Priscilla Morrison, PsyD)","East Brunswick","","",2,"Pediatric neuropsychologist: ADHD, learning difficulties, autism; school observation","Psychology Today","1","","Medium","Part of the Center for CBT group or her own practice?","individual"),
("Stephanie Cooper, PsyD","Somerset","","",3,"Learning evaluations (IQ and achievement); former child study team psychologist","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
("Wendy Skiba-King, PhD, APN","Somerset","","",3,"Autism spectrum and ADHD","Psychology Today","1","","Medium","Practice name, website, phone.","individual"),
("Children's Wellness & Developmental Center","Middlesex County (town unconfirmed)","","",3,"Outpatient services listed for Mercer, Middlesex, Monmouth and Ocean counties","Monmouth ResourceNet","","","High","Which town is the Middlesex office? May be based outside the target counties."),
],spec="Mental health")
# -------- primary care (family medicine, internal medicine, pediatrics)
PC_CHK="Confirm it is clinician-owned (not RWJBarnabas, Hackensack Meridian, Atlantic Health, Saint Peter's, Hunterdon, Penn Medicine or a PE platform). Count physicians. Website and Google profile?"
add2("primary_care","Family medicine",[
("Avenel Iselin Medical Group, LLC","Iselin","400 Gill Ln","",2,"LLC; family medicine provider listed (accepting new patients, telehealth)","Medifind","","","Medium",PC_CHK),
("Family Medicine & Dentistry of East Brunswick","East Brunswick","647 NJ-18","",2,"Offers primary medical and dental care together","Zocdoc","","","Medium",PC_CHK),
("Highland Park Family Practice","Highland Park","505 Raritan Ave","",3,"Listed in a Robert Wood Johnson Barnabas community directory","RWJBH directory","","","High","Listing in a RWJBH directory suggests possible system ownership. Check for RWJPE branding. "+PC_CHK),
("Etheridge Family Medicine","Somerset","","",2,"Telehealth offered; hospital affiliations listed at Hunterdon, RWJ and Saint Peter's","Cureus profile","","","Medium",PC_CHK),
("Practice Associates Medical Group","Branchburg","3322 Route 22","",2,"Family medicine providers accepting new patients; also appears in the cardiology list as a multi-specialty group","Directory listing","","Medium","Medium","Multi-specialty group: count providers; same company as the cardiology row?","","Suspected: multi-specialty group"),
("Faculty Family Practice at Somerset, LLC","Somerville","110 Rehill Ave","",3,"Not on Medicare; no telehealth; address next to the RWJ Somerset campus","Cortico directory","","","High","Probably tied to the RWJ family medicine residency faculty. Likely system-linked: confirm before keeping."),
("Central Jersey Medical Center","Perth Amboy","","",3,"Federally qualified health center with sites in Perth Amboy and Carteret; hiring","Job posting","","Large","Low","FQHC (nonprofit, different buyer): filter out.","","Evidence: FQHC with multiple sites"),
],spec="Family medicine")
add2("primary_care","Internal medicine",[
("Internal Medicine of North Brunswick","North Brunswick","2300 Route 27, Suite 1A","",3,"Listed in a RWJBH community directory","RWJBH directory","","","High","Listing in a RWJBH directory suggests possible system ownership. "+PC_CHK),
("Medical Associates of Central New Jersey","Old Bridge","26 Throckmorton Ln","",2,"Internal medicine primary care provider listed","Directory listing","","","Medium",PC_CHK),
("SD Medical","Spotswood","407 Main St, Suite 1","",2,"Internal medicine providers listed","Directory listing","","","Medium",PC_CHK),
("South Plainfield Primary Care","South Plainfield","2509 Park Ave","",2,"NPI record lists family and internal medicine; last updated January 2022. Same address as Clear Conscience Counseling (mental health list)","NPI listing","","","High","Still open? Shares a building with another listing."),
("Internal medicine practice at 1636 Stelton Rd, Suite 301 (name unconfirmed)","Piscataway","1636 Stelton Rd, Suite 301","",3,"Zocdoc listing: individualized treatment plans, 25+ years of experience","Zocdoc","","","High","Find the practice name and owner."),
("MDVIP concierge practice (225 May St)","Edison","225 May St","",3,"MDVIP concierge internal medicine; physician-owned, membership model","MDVIP directory","1","","Medium","Different offer (membership). Physician name, website, own marketing?","","Evidence: MDVIP physician-owned network"),
("MDVIP concierge practice (267 Central Ave)","Metuchen","267 Central Ave","",3,"MDVIP concierge internal medicine; membership model","MDVIP directory","1","","Medium","Different offer (membership). Physician name, website, own marketing?","","Evidence: MDVIP physician-owned network"),
("Lijing Shen, MD","Edison","906 Inman Ave","",3,"Internist","Medifind","1","","Medium","Practice name, website, phone.","individual"),
("Harry Lin, MD","Metuchen","201 Bridge St","",3,"Internist","Medifind","1","","Medium","Practice name, website, phone.","individual"),
("Inderjit Kainth, MD","South Brunswick","","",3,"Internist; offices in South Brunswick, Kendall Park and Metuchen","Zocdoc","1","","Medium","Practice name, website, phone. Three offices: still solo?","individual"),
("Jeffrey Kaladas, MD","South Bound Brook","","",3,"Internist; accepting new patients","Zocdoc","1","","Medium","Practice name, website, phone.","individual"),
("Rizwana Khan, MD","Old Bridge","2477 County Rd 516, Unit 103","",3,"Primary care / internal medicine","Zocdoc","1","","Medium","Practice name, website, phone.","individual"),
],spec="Internal medicine")
add2("primary_care","Pediatrics",[
("Pediatric & Adolescent Associates of Central NJ","Old Bridge","100 Perrine Rd","",2,"WebMD: not accepting new patients; no Medicaid or Medicare listed (may be outdated)","WebMD","","","High","Open and accepting patients? Count pediatricians."),
("Somerset Pediatric Group","Bridgewater","2345 Lamington Rd","",3,"Founded 1958; offices in Hillsborough, Bedminster, Warren, Lebanon, Somerset, Raritan, Long Valley, Springfield and Highland Park","Practice site","","Large","Low","Large multi-office group: filter unless you want a bigger target. Who handles its marketing?","","Evidence: ten offices listed"),
("Pediatric Associates of Hillsborough","Hillsborough","349 Doctors Way","(908) 431-5352",3,"Listing says affiliated with Primary Care Partners in partnership with Atlantic Health System","Macaroni Kid directory","2","","High","Affiliation with Atlantic Health: confirm ownership before keeping.","","Evidence: listing names the Atlantic Health partnership"),
("Edison Health (pediatrics)","Edison","Route 27","",2,"Pediatrician Shelley Carolan sees patients here; accepting new patients","Zocdoc","","","Medium",PC_CHK),
("Shelley Carolan, MD","Edison","Route 27 (Edison Health)","",3,"Board-certified pediatrician","Zocdoc","1","","Medium","Employed by Edison Health or owner?","individual"),
("Laura Senator, MD","Hillsborough","349 Doctors Way","",3,"Pediatrician at Pediatric Associates of Hillsborough","Macaroni Kid directory","1","","Medium","Part of the Hillsborough practice above.","individual"),
],spec="Pediatrics")
# -------- size marking for existing rows (basis stated)
MARK={ # name: (override, basis)
"Strive Physical Therapy of Monroe":("Large","Evidence: 18-location network"),
"Ivy Rehab Physical Therapy (Piscataway)":("Large","Evidence: 130+ NJ locations per its release"),
"Ivy Rehab Physical Therapy (Somerset)":("Large","Evidence: 130+ NJ locations per its release"),
"Professional Physical Therapy (Edison)":("Large","Evidence: multi-office network; acquired Somerset Family PT in 2022"),
"Professional Orthopedic and Sports Physical Therapy of NJ":("Large","Suspected: may belong to the Professional PT network"),
"Kessler Rehabilitation Center - Somerset":("Large","Suspected: Kessler is a multi-site rehab brand"),
"Kessler Rehabilitation Center - Bernardsville":("Large","Suspected: Kessler is a multi-site rehab brand"),
"FOX Rehabilitation":("Large","Suspected from general knowledge: FOX operates many clinics; verify"),
"JAG Physical Therapy":("Medium","Suspected: several clinics (North Brunswick, Old Bridge x2, Whiting)"),
"FYZICAL Monroe Township":("Medium","Suspected: franchise network, each site locally owned"),
"FYZICAL Green Brook":("Medium","Suspected: franchise network, each site locally owned"),
"Primecare Medical Group":("Large","Evidence: multi-site multi-specialty group recruiting cardiologists"),
"The Eye Care & Surgery Center":("Large","Evidence: listed as an affiliate of Prism Vision Group"),
"Associated Retinal Consultants":("Large","Suspected: appears to be part of a larger multi-state retina group"),
"Omni Eye Services":("Large","Suspected: described as a multi-subspecialty group"),
"NJRetina":("Large","Suspected: multi-location retina group"),
"Eastern Dental of Woodbridge LLC":("Large","Suspected: Eastern Dental is a multi-office brand"),
"Eastern Dental of Old Bridge":("Large","Suspected: Eastern Dental is a multi-office brand"),
"Gentle Dental of Branchburg":("Large","Suspected: Gentle Dental is a multi-office group"),
"KK Dental":("Medium","Suspected: KK Dental also has a Somerset office"),
"KK Dental Associates - Somerset":("Medium","Suspected: KK Dental also has an Edison office"),
"NuvSmile":("Large","Suspected: NuvaSmile advertises for a 'traveling periodontist', implying many offices"),
"Metuchen Group Dental LLC":("Medium","Suspected: group name"),
"The Dentists of Woodbridge":("Medium","Suspected: two dentists listed under one name"),
"Monroe Dental Group LLC":("Medium","Suspected: group name"),
"Bridgewater Dental Group":("Medium","Suspected: group name; includes a periodontist"),
"The Star Dental Group":("Medium","Suspected: group name"),
"Soft Care Dental Group":("Medium","Suspected: group name"),
"Central Jersey Pediatric Dentistry & Orthodontics":("Medium","Suspected: a pediatric dentist and an orthodontist under one name"),
"Cardio MD":None,
"Primecare Medical Group (primary care)":None,
}
for r in rows:
    m=MARK.get(r["practice"])
    if m:
        if not r["size_override"]: r["size_override"]=m[0]
        r["size_basis"]=m[1]
    elif r["size_override"] and not r["size_basis"]:
        r["size_basis"]="Evidence/suspicion in the evidence column"
# -------- write split files (data/candidates) and a master
import collections, csv as _csv
HH=H+["segment","subspecialty","size_basis"]
def split_key(r): return f"{r['segment']}_{'individuals' if r['kind']=='individual' else 'practices'}"
cnt=collections.Counter(split_key(r) for r in rows)
for key in cnt:
    sub=[r for r in rows if split_key(r)==key]
    sub.sort(key=lambda r:(r["subspecialty"],r["city"],r["practice"]))
    with open(f"data/candidates/{key}.csv","w",newline="",encoding="utf-8") as fh:
        w=_csv.DictWriter(fh,fieldnames=HH); w.writeheader(); w.writerows([{k:r.get(k,"") for k in HH} for r in sub])
with open("data/candidates/ALL_candidates.csv","w",newline="",encoding="utf-8") as fh:
    w=_csv.DictWriter(fh,fieldnames=HH); w.writeheader(); w.writerows([{k:r.get(k,"") for k in HH} for r in rows])
print(dict(cnt), "total", len(rows))
sizes=collections.Counter((r["segment"],r["size_override"]) for r in rows if r["size_override"]); print(dict(sizes))
