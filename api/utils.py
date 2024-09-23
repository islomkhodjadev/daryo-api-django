import os

from openai import OpenAI

from dotenv import load_dotenv

load_dotenv()

import os

content = (
    open("text.txt").read()
    + """\n secondly write always including emojies you must use emojies a lot,
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
<blockquote expandable>Expandable block quotation started\nExpandable block quotation continued\nExpandable block quotation continued\nHidden by default part of the block quotation started\nExpandable block quotation continued\nThe last line of the block quotation</blockquote>"""
)


def get_ai_response(user_message, content=content, extra_data=None):

    client = OpenAI(api_key=os.getenv("GPT_TOKEN"))

    if extra_data is not None:
        content += extra_data

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        messages=[
            {"role": "system", "content": content},
            {"role": "user", "content": user_message},
        ],
    )

    ai_response = completion.choices[0].message

    return ai_response.content
