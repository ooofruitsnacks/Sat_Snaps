# Sat_Snaps
It's a bird... it's a plane... no its a space camera!! Take satellite pictures of whatever location you want using Apple's native MapKit because f%#@ google API keys and their reduced image quality.


EX:


<img width="1920" height="1080" alt="satmap_-37 81360_144 96310" src="https://github.com/user-attachments/assets/6f665228-d94b-4579-9a4f-da044d99372c" />



# Welcome
Sat_Snaps is designed for Mac users currently but I'm working hard at porting this over to other platforms eventually.


### Install dependencies (REQUIRED)
1.Homebrew


2.Python3


3.pyobjc-framework-MapKit


4.pyobjc-framework-CoreLocation


5.pyobjc-framework-Quartz

# Install Dependencies Guide
After you've installed python3 in Homebrew run this command.

`python3 -m venv path/to/venv
  source path/to/venv/bin/activate
  python3 -m pip install pyobjc-framework-MapKit pyobjc-framework-CoreLocation pyobjc-framework-Quartz`

  ### HOW THIS COMMAND WORKS

  `python3 -m venv path/to/venv
  source path/to/venv/bin/activate` will setup a virtual environment for python3, I recommend doing it this way instead of giviing python3 systemwide access. 


  `python3 -m pip install pyobjc-framework-MapKit pyobjc-framework-CoreLocation pyobjc-framework-Quartz` will install the dependencies required to run Sat_Snaps.

  now hit command+Q to close the terminal


  # OPEN A NEW VIRTUAL ENVIRONMENT AND RUN SAT_SNAPS
`python3 -m venv path/to/venv
  source path/to/venv/bin/activate && python3 Sat_Snaps.py`


  Running the command will start a virtual environment and open Sat_Snaps (pre-congifured examples shown)
  

  <img width="605" height="518" alt="Screenshot 2026-05-14 at 1 46 33 PM" src="https://github.com/user-attachments/assets/7238003b-8f6e-4bc6-a776-85eadeac58ab" />
  

  Choose whatever location you want and wait a few seconds, the full size preview image will pop up, if you like the placement and the zoom settings you can close the image because the option to save it is in another tab. 
  
  
  (example below: im working on getting that tab to load above the image, I know it's annoying)
  

  <img width="421" height="350" alt="Screenshot 2026-05-14 at 1 47 19 PM" src="https://github.com/user-attachments/assets/26f2cbe0-f73a-4f68-bda9-ae4bc695a57b" />


  To exit Sat_Snaps just type exit and hit enter.


  <img width="760" height="306" alt="Screenshot 2026-05-14 at 1 47 47 PM" src="https://github.com/user-attachments/assets/e26db74b-feda-4602-8286-72e89a901b64" />




  Have Fun! Instructions on how to edit locations and zoom settings will be below. 


  # CHANGE LOCATIONS, RESOLUTION, AND ZOOM
  Open your preferred text editor and open the Sat_Snaps.py source code file.
  

  ### LOCATIONS


  You can add/change locations starting on Line 32, just follow the same format.


  ### RESOLUTION AND ZOOM


On lines 232 and 399, make sure the lat and lng width's/height's/span degrees all match. It is preset to 1920x1080 which is optiimized to the best qaulity settings currently. You can increase the span degree to zoom out EX: 0.0050 or you can zoom in by decreasing the span degree EX: 0.0006. After all changes have been saved to the file, run the commands to open a virtual environment and run the Sat_Snaps command. 

  
  
  
