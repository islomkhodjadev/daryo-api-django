import os

from openai import OpenAI

from dotenv import load_dotenv
from .models import AiData, Category, Conversation

load_dotenv()

import os

content = """\n 
you are well taught assistant of 'Daryo' news company,
do not change the name of the company always 'Daryo' in any language,
you are like professional journalist helper, but you answer to questions and responses

some info about daryo:
Channel Title: Daryo.uz
Link: https://daryo.uz/en
Description: Daryo is a comprehensive online news company that delivers the latest information, unbiased analysis, columnists' blogs, and corroborated facts.

firstly write in language of user's language mainly in uzbek, but if the request was in other language answer in user's language,

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


def ai(content, user_message):

    client = OpenAI(api_key=os.getenv("gpt_token"))

    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.4,
        max_tokens=500,
        messages=[
            {"role": "system", "content": content},
            {"role": "user", "content": user_message},
        ],
    )

    ai_response = completion.choices[0].message
    return ai_response.content


def chooseOne(user_message):
    global content

    permanent_content = content
    token_used = len(permanent_content)

    content_for_chooser = (
        """
    your main and only goal is to choose relative data category  
    and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen category if doesnt exists 
    then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
    headings from which yous should choose, data will be in "id:({data.id})-category:({data.category});" format here are they:::
    """
        + Category.getAllCategories()
    )
    token_used += len(content_for_chooser)

    category = Category.getData(ai(content_for_chooser, user_message))

    if category is not None:

        content_for_chooser = """
        your main and only goal is to choose relative data heading  
        and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen heading if doesnt exists 
        then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
        headings from which yous should choose, data will be in "id:({data.id})-category:({data.heading});" format here are they:::
        """ + AiData.getAllHeadingsByCat(
            category.id
        )
        token_used += len(content_for_chooser)

        aidata = AiData.getData(ai(content_for_chooser, user_message))

        if aidata is not None:
            token_used += len(aidata.content)

            permanent_content += aidata.content

    return permanent_content, token_used // 4


from django.conf import settings


def get_ai_response(user_message, user_history):

    permanent_data, token_used_input = chooseOne(user_message)

    if settings.HISTORY_ALLOWED:

        user_message = user_history

    token_used_input += len(user_message) // 4

    answer = ai(permanent_data, user_message)
    token_used_output = (len(answer) // 4) + 6

    return answer, token_used_input, token_used_output


from functools import lru_cache


def token_size_calculate(user_history):
    global content

    length = len(content)

    content_for_chooser = (
        """
    your main and only goal is to choose relative data category  
    and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen category if doesnt exists 
    then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
    headings from which yous should choose, data will be in "id:({data.id})-category:({data.category});" format here are they:::
    """
        + Category.getAllCategories()
    )

    length += len(content_for_chooser)

    content_for_chooser = """
        your main and only goal is to choose relative data heading  
        and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen heading if doesnt exists 
        then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
        headings from which yous should choose, data will be in "id:({data.id})-category:({data.heading});" format here are they:::
        """

    length += len(content_for_chooser)

    token_size = length // 4

    token_size += Category.calculate_average_headings_token_by_cat()
    token_size += AiData.getMeanContentLength() // 4

    if settings.HISTORY_ALLOWED:
        token_size += len(user_history) // 4

    return token_size


def avarage_request_token_size():

    length = len(content)

    content_for_chooser = (
        """
    your main and only goal is to choose relative data category  
    and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen category if doesnt exists 
    then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
    headings from which yous should choose, data will be in "id:({data.id})-category:({data.category});" format here are they:::
    """
        + Category.getAllCategories()
    )

    length += len(content_for_chooser)

    content_for_chooser = """
        your main and only goal is to choose relative data heading  
        and returning it's id the number only id number not any other characters only the id number e.g like id:(0) you shoulld return the number 0 only inside, dont return other thing just id of choosen heading if doesnt exists 
        then you can return id which is similiar or relative to question in the worst the worst case return the relative similiar id , you must return only number not other thing in any case here are the 
        headings from which yous should choose, data will be in "id:({data.id})-category:({data.heading});" format here are they:::
        """

    length += len(content_for_chooser)

    token_size = length // 4

    token_size += Category.calculate_average_headings_token_by_cat()
    token_size += AiData.getMeanContentLength() // 4
    if settings.HISTORY_ALLOWED:
        token_size += Conversation.get_avarage_token_size_for_history()

    return token_size
