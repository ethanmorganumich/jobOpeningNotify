cd /Users/emorgan/Documents/FunProjects/jobOpeningNotify;
source jobNotify/bin/activate;
pip freeze > requirements.txt
mv requirements.txt ./lambda_deploy
cd ./lambda_deploy
pip install -r requirements.txt -t .
cp ../openai.py .
mv openai.py lambda_handler.py
rm ../lambda_package.zip
zip -r ../lambda_package.zip .