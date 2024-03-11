import json
import re
import csv
import base64
from openai import OpenAI
import openai
import json
from tqdm import tqdm
import os
import pdb
from pathlib import Path
from collections import defaultdict
import argparse
from tqdm import tqdm
parser = argparse.ArgumentParser()
parser.add_argument("--model_name", type=str, default ='model' )
parser.add_argument("--answer_file_path", default = "example.jsonl", type=str)
parser.add_argument("--output_dir", type=str)
parser.add_argument("--openai_key", type=str)
args = parser.parse_args()
base_dir = os.getcwd()
if not args.output_dir:
    args.output_dir = f"log_{args.model_name}"
client = OpenAI(api_key=args.openai_key)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')



output_dir = args.output_dir 
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
jsonl_file_path = args.answer_file_path
scores_by_category = defaultdict(list)
total_lines = sum(1 for line in open(jsonl_file_path, 'r', encoding='utf-8'))
with open(jsonl_file_path, 'r', encoding='utf-8') as file:
    for line in tqdm(file, total=total_lines):
        # Parse the JSON object from each line
        item = json.loads(line)
        if 'ground truth' not in item or 'answer' not in item or 'question' not in item:
            continue 
        true_descriptions = item['ground truth']
        generated_description = item['answer']
        question = item['question']

        prompt = f"""
        Given a question about an image, there is a correct answer to the question and an answer to be determined. If the correctness of the correct answer is given a score of 5, please rate the correctness of the answer to be determined(1 to 5 points).
        
        Question:
        - question about the image: {question}\n
        
        Answers:
        - correct answer(ground truth): {true_descriptions}\n
          answer to be determined: {generated_description}\n
          
        Task:\n
        - Given a question about an image, there is a correct answer to the question and an answer to be determined. If the correctness of the correct answer is given a score of 5, please rate the correctness of the answer to be determined(1 to 5 points).
        
        Output Format:
        Similarity: your answer\n
        """
        path = item['path']
        # print(base_dir)
        image_path = f"""{base_dir}{path}"""
        # print(image_path)
        # image_data = encode_image(path)
        if os.path.exists(image_path):
            image_data = encode_image(image_path)
        else:
            continue

        response = client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_data}",
                                "detail": "low"
                            }
                        },
                    ],
                }
            ],
            max_tokens=100,
        )


        _, main_category, subcategory, _ = path.split('/')
        gpt_response = response.choices[0].message.content  
        item['gpt_response'] = gpt_response
        try:
            match = re.search(r'\b[0-5](?:\.\d+)?\b', gpt_response.split('Similarity:')[1])
            score = int(match.group(0)) 
            scores_by_category[f"{main_category}/{subcategory}"].append(score)
            subcategory_safe = subcategory.replace('/', '_')
            subcategory_file_path = f"{output_dir}/{main_category}_{subcategory_safe}.jsonl"
            item["score"] = score
            with open(subcategory_file_path, 'a') as subcategory_file:
                json.dump(item, subcategory_file)
                subcategory_file.write('\n')            
        except ValueError:
            print(f"Error: The response '{gpt_response}' is not a valid integer and will be skipped.")


for category_path, scores in scores_by_category.items():
    main_category, subcategory = category_path.split('/', 1)
    average_score = sum(scores) / len(scores)
    print(f'Main Category: {main_category}')
    print(f'Average score for {subcategory}: {average_score:.2f}\n')

