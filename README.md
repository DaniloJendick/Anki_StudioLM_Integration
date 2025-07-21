
# Anki_StudioLM_Integration
    Anki StudioLM Integration
    The idea of this addon is to connect Anki to Studio LM, so we can integrate this two open source softwares. 
    I tried to make it user friendly, but, we have to CMD to start the server. 
    Disclaimer: If the results are weak/bad try using a bigger model and also try to make good prompts. the results are the same as Studio LM.


Quick Setup (First Time Users)    
    Step 1: Install & Start LM Studio (skip if you already have this installed)
        1   Download and install LM Studio - https://lmstudio.ai/
        2   Download a model (any chat model works - try llama-3.2 or similar)
            2.1 Click on Discovery -> Model Search -> choose one you like and download it.
        3   Select and load the model
            3.1 Go to the Chat tab in LM Studio
            3.2 Click "Select a model to load" at the top
            3.3 Choose your downloaded model from the list
            3.4 Wait for it to load (you'll see "Model loaded" message)
    
    Step 2: Start the local server
        1   Click on Discovery -> App Settings -> Developer -> Check "Enable Local LLM Service"
        2   Start Local Server
            2.1 Linux/Mac open the command line   
                # First time only (bootstrap):
                ~/.lmstudio/bin/lms bootstrap
                # Then use normally:
                lms server start
            2.1 on Windowns open the command line
                lms server start
    
    Step 3: Dowload the Anki Addon
        1   Open your Anki go to "tools" -> addons -> Get Addons -> insert XXXXXXX -> restart Anki. 

    Step 4: Test connection
        1   Open Anki go to "Browser" -> Click on the dropdown "LM Studio" -> click on "Test Connection"
            1.1 in case of errors try redoing last steps, in case the error persists, contact me.

    Step 5: Output Field Configuration
        1   On the dropdown "LM Studio" -> go to "Configure Fields" - on Target Field, put the field of your note that will receive the output and then click on "Save Configuration". 
        2   Feel Free to test the other functions like "Prefered Model", "Load Model",

    Step 6: Configure System Prompt and User Prompt. 
        Context: System prompt: Instructions given to an AI model before any user interaction that define its behavior, personality, capabilities, and constraints. Sets the foundational context for how the model should respond.
        Context: User prompt: The actual input/question/request from a human user that the AI responds to.
        1   On the dropdown "LM Studio" -> go to "Prompt Configuration".
        2   Write the System Prompt.
        3   Write the User Prompt. 
            3.1 to use your anki note fields, write the name of the field between {{}}, for example {{Front}}, {{English}}, you are not limited on which fields you can use. it does not work on image/audio fields.
        4   Set the Temperature, (personal note, I use it as low as possible, I just left this because it may have a few use-cases)
        5   Save Configuration
    
    Step 7: Select Cards and Process
        1   Select all the cards that you want to use your prompt
        2   On the dropdown "LM Studio" -> "Process Selected Notes" 
        3   Wait and see. 

        

    





