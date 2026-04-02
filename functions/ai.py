from openai import OpenAI
import json
import config


def open_ai(author, msg):
    api_key = config.OPENAI_API_KEY
    
    client = OpenAI(api_key=api_key)
    
    with open("prompt.json", "r", encoding='utf8') as f:
        messages = json.load(f)
    msg_deal = f"{author}: {msg}"
    messages.append({"role": "user", "content": msg_deal})

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    if response.choices[0].message.content == "!@Q":
        messages.pop(-1)
        return None
    else:
        messages.append(
            {"role": "assistant", "content": response.choices[0].message.content})
        if len(messages) >= 16:
            while len(messages) != 16:
                messages.pop(1)

    with open('prompt.json', 'w', encoding='utf8') as f:
        json.dump(messages, f,
                  ensure_ascii=False, indent=4)

    if response.choices[0].message.content[0:5] == "小魅魔: ":
        return response.choices[0].message.content[5:]
    else:
        return response.choices[0].message.content
