import google.generativeai as genai
genai.configure(api_key="AIzaSyAKbtJyypvjhUii916BcqpAHeprwZWW3Dc")
for m in genai.list_models():
    print(m.name)
