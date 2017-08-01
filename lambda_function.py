# -*- coding: utf-8 -*-
"""
Sample skill of Alexa
  - Here tuser request to get a companies' stock price.
  - But always answer the Nomura holdings's price
"""

import contextlib
import feedparser
import json
import logging
import random
import re
import traceback
import urllib

APPLICATION_ID="amzn1.ask.skill.3cd5acae-66d2-41ae-8b06-eb2ce5552e85"

# write log to CloudWatch log
Logger = logging.getLogger()
Logger.setLevel(logging.INFO)

Text = {
    "welcome": {
        "title": "Welcome",
        "speech": """Welcome to fuji bot. 
        I can tell you stock prices of any companies.
        Ask 'how much is the stock price of some company'
        """,
        "reprompt": """Please ask how much the stock price of a company is,
        or I can tell you some news.
        Just say news.
        """
    },
    "price": {
        "title": "Price",
        "speech_org_1": "the price of nomura holding's is\n\n %s yen",
        "speech_org_2": """I don't know about %s. 
        But I know the price of nomura holding's is\n\n %s yen
        """,
        "speech": "",
        "reprompt": "Please ask how much the stock price of a company is"
    },
    "real_price": {
        "title": "Price",
        "speech_org": "the price of %s is\n\n %s yen",
        "speech": "",
        "reprompt": "Please ask how much the stock price of a company is"
    },
    "price_unknown": {
        "title": "Unknown Request",
        "speech": """I cannot hear the company name.
        Please ask like 'how much is the stock price of some-company-name'
        """,
        "reprompt": "Please ask how much the stock price of a company is"
    },
    "news": {
        "title": "News",
        "speech_company": "Fuji bot tell you the news about %s\n\n",
        "speech_business": "Fuji bot tell you business news\n\n",
        "reprompt": "Say\n Next\n if you'd like to listen the other news"
    },
    "help": {
        "title": "Help",
        "speech": """Please specifiy the company name by asking
        'how much is the stock price of some-company-name?'
        """,
        "reprompt": """Please ask how much the stock price of a company is,
        or\n I can tell you some news
        """
    },
    "unknown": {
        "title": "Unknown Request",
        "speech": """I can't understand your request.
        Please ask the stock price of some company
        or\n I can tell you some news
        """,
        "reprompt": "Please ask how much the stock price of a company is"
    },
    "error": {
        "title": "Error",
        "speech": """Something wrong within Fuji bot system.
        I'm sorry for the inconvenience, 
        but it doesn't do anything useful, anyway.
        """,
        "reprompt": None
    },
    "finish": {
        "title": "Session Ended",
        "greetings": ["Have a nice day!", "Goodbye", "See you next time!"],
        "speech_org": "Thank you for trying Fuji bot, %s",
        "reprompt": None
    }
}

IDS_API_ENDPOINT = "http://13.55.87.145/v1/api/"

class RequestHandler:
    def __init__(self, request, session):
        self.request = request
        self.session = session
        if session.has_key('attributes'):
            self.attributes = session['attributes']
        else:
            self.attributes = {}
        if request.has_key('intent'):
            self.intent = request['intent']

    def info(self, msg):
        Logger.info("PROC: (%s, %s) %s", self.request['requestId'],
                    self.session['sessionId'], msg)

    def welcome(self):
        self.attributes = {}
        return self.response('welcome')

    def finish(self):
        idx = random.randint(0,2)
        greetings = Text['finish']['greetings'][idx]
        Text['finish']['speech'] = Text['finish']['speech_org'] % (greetings)
        return self.response('finish', True)

    def unknown(self):
        return self.response('unknown')
    
    def user_help(self):
        return self.response('help')
        
    def error(self):
        return self.response('error', True)
    
    def price(self):
        company = self._get_company_name()
        if company == None:
            return self.response('price_unknown')
        price = self._get_price()
        self.info("company: %s, price: %s" % (company, price))

        self._set_price_speech(company, price)
        return self.response('price')

    def real_price(self):
        company = self._get_company_name()
        if company == None:
            return self.response('price_unknown')
        price = self._get_real_price(company)
        if price == None:
            return self.response('price_unknown')
        self.info("company: %s, price: %s" % (company, price))

        speech = Text['real_price']['speech_org'] % (company, price)
        Text['real_price']['speech'] = speech
        return self.response('real_price')
        
    def _get_company_name(self):
        if not self.intent['slots'].has_key('Company'):
            return None
        if not self.intent['slots']['Company'].has_key('value'):
            return None
        return self.intent['slots']['Company']['value']
        
    def _get_price(self):
        # get closing stock price of 8604 (nomura)
        url = 'https://www.google.com/finance/getprices?q=8604&x=TYO&i=300&p=30m&f=d,h'
        with contextlib.closing(urllib.urlopen(url)) as f:
            data = f.read()
        for line in data.split("\n"):
            m = re.match(r"^a[0-9]*,([0-9.]*)", line)
            if m:
                return m.group(1)

    def _get_real_price(self, company):
        url = IDS_API_ENDPOINT + "/corporations/attribute.json?eng=" + company.upper()
        with contextlib.closing(urllib.urlopen(url)) as f:
            data = json.load(f)
        if len(data['response']) == 0:
            return None
        self.info(json.dumps(data))
        # XXX: 複数ヒットした場合は先頭の企業を取ってしまっている
        oldcd = data['response'][0]['oldcd']

        url = IDS_API_ENDPOINT + "/quotes/delayed.json?issueCode=" + oldcd
        with contextlib.closing(urllib.urlopen(url)) as f:
            data = json.load(f)
        if len(data['response']) == 0:
            return None
        return data['response'][0]['lastprice']

    def _set_price_speech(self, company, price):
        if company in ["nomura", "nomura holdings"]:
            speech = Text['price']['speech_org_1'] % (price)
        else:
            speech = Text['price']['speech_org_2'] % (company, price)
        Text['price']['speech'] = speech

    def news(self):
        if not (self.intent['slots'].has_key('Company')
                and self.intent['slots']['Company'].has_key('value')):
            gnews = self._get_business_news()
            Text['news']['speech'] = Text['news']['speech_business']
        else:
            company = self.intent['slots']['Company']['value']
            gnews = self._get_company_news(company)
            Text['news']['speech'] = Text['news']['speech_company'] % (company)
        self.attributes['news_entries'] = json.dumps(gnews)
        self.attributes['news_count'] = 1
        if len(gnews) == 0:
            return self.response('unknown')
        Text['news']['speech'] = Text['news']['speech'] + gnews[0]
        return self.response('news')
        
    def _get_company_news(self, company):
        gnews_url = "https://news.google.com/news/section?hl=en&q=%s&output=rss"
        return self._extract_news(feedparser.parse(gnews_url % (company)))
        
    def _get_business_news(self):
        gnews_url = "https://news.google.com/news/section?hl=en&topic=b&output=rss"
        return self._extract_news(feedparser.parse(gnews_url))
        
    def _extract_news(self, feed):
        news = []
        for entry in feed.entries:
            news.append(self._format_news(entry))
        return news    
        
    def _format_news(self, entry):
        title = entry['title']
        description = re.sub(r'&[^;]+;', '',
                             re.sub(r'<[^>]+>', '', entry['description']))
        return title + "\n" + description
        
    def next(self):
        if not self.attributess.has_key('news_entries'):
            return self.response('unknown')
        gnews = json.loads(self.attributes['news_entries'])
        count = self.attributes['news_count']
        if len(gnews) <= count:
            return self.response('unknown')
        Text['news']['speech'] = gnews[count]
        self.attributes['news_count'] = count + 1
        return self.response('news')
        
    def set_attribute(self, key, value):
        self.attributes[key] = value

    def response(self, intent, end=False):
        """
        Helper function to build response
        """
        title = Text[intent]['title']
        speech = Text[intent]['speech']
        reprompt = Text[intent]['reprompt']        
        return {
            'version': '1.0',
            'sessionAttributes': self.attributes,
            'response': {
                'outputSpeech': {
                    'type': 'PlainText',
                    'text': speech
                },
                'card': {
                    'type': 'Simple',
                    'title': "SessionSpeechlet - " + title,
                    'content': "SessionSpeechlet - " + speech
                },
                'reprompt': {
                    'outputSpeech': {
                        'type': 'PlainText',
                        'text': reprompt
                    }
                },
                'shouldEndSession': end
            }
        }

class EventHandler:
    def __init__(self, request_handler):
        self.request = request_handler.request
        self.session = request_handler.session
        self.request_handler = request_handler
        if self.session['new']:
            self.on_session_started()

    def info(self, topic, msg=''):
        Logger.info("%s: (%s, %s) %s", topic,
                    self.request['requestId'], self.session['sessionId'], msg)

    def on_session_started(self):
        """ 
        Called when the session starts. Session attribute
        initialization here.
        """
        self.info("SESSION_START")

    def on_launch(self):
        """ 
        Called when the user launches the skill without specifying what they
        want
        """
        self.info("LAUNCH")
        # Dispatch to your skill's launch
        return self.request_handler.welcome()

    def on_intent(self):
        """ 
        Called when the user specifies an intent for this skill 
        """
        if not (self.request.has_key('intent') and self.request['intent'].has_key('name')):
            self.info("INTENT", "unknown")
            self.request_handler.unknown()

        # Dispatch to your skill's intent handlers
        intent_name = self.request['intent']['name']
        self.info("INTENT", intent_name)
        if intent_name == "StockPriceIntent":
            return self.request_handler.price()
        elif intent_name == "RealStockPriceIntent":
            return self.request_handler.real_price()
        elif intent_name == "NewsIntent":
            return self.request_handler.news()
        elif intent_name in ["NextIntent", "AMAZON.NextIntent"]:
            return self.request_handler.next()
        elif intent_name in ["HelpIntent", "AMAZON.HelpIntent"]:
            return self.request_handler.user_help()
        elif intent_name in ["StopIntent", "AMAZON.CancelIntent"]:
            return self.request_handler.finish()
        else:
            return intent_handler.unknown()

    def on_session_ended(self):
        """ 
        Called when the user ends the session.
        Is not called when the skill returns should_end_session=true
        """
        self.info("SESSION_END")
        # add cleanup logic here

def lambda_handler(event, context):
    """ 
    Main handler. 
    Route the incoming request based on type (LaunchRequest, IntentRequest,
    etc.) The JSON body of the request is provided in the event parameter.
    """
    
    app_id = event['session']['application']['applicationId']
    if app_id != APPLICATION_ID:
        raise ValueError("Invalid Application ID: %s" % (app_id))

    request_handler = RequestHandler(event['request'], event['session'])
    try:
        event_handler = EventHandler(request_handler)
        req_type = event['request']['type']
        if req_type == "LaunchRequest":
            return event_handler.on_launch()
        elif req_type == "IntentRequest":
            return event_handler.on_intent()
        elif req_type == "SessionEndedRequest":
            return event_handler.on_session_ended()
        else:
            request_handler.set_attribute('Unknown Request Type', req_type)
            Logger.error("Unknown request type: %s", req_type)
            return request_handler.error()
    except Exception as e:
        stacktrace = traceback.format_exc()
        Logger.error(stacktrace)
        request_handler.set_attribute('Stacktrace', stacktrace)
        return request_handler.error()

