import os

from openai import OpenAI

from dotenv import load_dotenv
from .models import AiData

load_dotenv()

import os

content = """\n 
some info about daryo:
Channel Title: Daryo.uz
Link: https://daryo.uz/en
Description: Daryo is a comprehensive online news company that delivers the latest information, unbiased analysis, columnists' blogs, and corroborated facts.
secondly write always including emojies you must use emojies a lot,
    thirdly when writing include your text into these formatting tags only these ones dont use others not any sings like **.
    always remembrer always format your answers accordingly: 
    <b>bold</b>, <strong>bold</strong>
<i>italic</i>, <em>italic</em>
<u>underline</u>, <ins>underline</ins>
<s>strikethrough</s>, <strike>strikethrough</strike>, <del>strikethrough</del>
<span class="tg-spoiler">spoiler</span>, <tg-spoiler>spoiler</tg-spoiler>
<b>bold <i>italic bold <s>italic bold strikethrough <span class="tg-spoiler">italic bold strikethrough spoiler</span></s> <u>underline italic bold</u></i> bold</b>
<a href="http://www.example.com/">inline URL</a>
<a href="tg://user?id=123456789">inline mention of a user</a>
<tg-emoji emoji-id="5368324170671202286">👍</tg-emoji>
<code>inline fixed-width code</code>
<pre>pre-formatted fixed-width code block</pre>
<pre><code class="language-python">pre-formatted fixed-width code block written in the Python programming language</code></pre>
<blockquote>Block quotation started\nBlock quotation continued\nThe last line of the block quotation</blockquote>
<blockquote expandable>Expandable block quotation started\nExpandable block quotation continued\nExpandable block quotation continued\nHidden by default part of the block quotation started\nExpandable block quotation continued\nThe last line of the block quotation</blockquote>


here is is info you should know and answer from:\n
"""


content_for_chooser = (
    """
your main and only goal is to choose relative data heading  
and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen heading if doesnt exists 
then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
headings from which yous hould choose, data will be in "id:({data.id})-heading:({data.heading});" format here are they:::
"""
    + AiData.getAllHeadings()
)


def get_ai_response(user_message, user_history, content=content, extra_data=None):
    client = OpenAI(api_key=os.getenv("gpt_token"))

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": content_for_chooser},
            {"role": "user", "content": user_message},
        ],
    )

    ai_response = completion.choices[0].message
    print(ai_response.content)
    data = AiData.getData(ai_response.content)
    print(data)
    permanent_data = content
    if data is not None:
        permanent_data += data.content

    if extra_data is not None:
        content += extra_data

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": permanent_data},
            {"role": "user", "content": user_history},
        ],
    )

    ai_response = completion.choices[0].message

    return ai_response.content
