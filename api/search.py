from sqlalchemy import and_
from sqlalchemy import or_

from tuser import TUser
from tweet_entity import TweetEntity
from tweet import Tweet

from util import beta_predicate_users

import logging

class AndToken:
    def __repr__(self):
        return 'AndToken[]'
    def __str__(self):
        return '+'

class OrToken:
    def __repr__(self):
        return 'OrToken[]'
    def __str__(self):
        return ' '

class OpeningParenthesesToken:
    def __repr__(self):
        return 'OpeningParenthesesToken[]'
    def __str__(self):
        return '('

class ClosingParenthesesToken:
    def __repr__(self):
        return 'ClosingParenthesesToken[]'
    def __str__(self):
        return ')'

class HashtagToken:
    def __repr__(self):
        return 'HashtagToken[]'
    def __str__(self):
        return '#'

class MentionToken:
    def __repr__(self):
        return 'MentionToken[]'
    def __str__(self):
        return '@'

class ColonToken:
    def __repr__(self):
        return 'ColonToken[]'
    def __str__(self):
        return ':'

class StringCharacterToken:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'StringCharacterToken[' + repr(self.value) + ']'

    def __str__(self):
        return self.value

class StringToken:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'StringToken[' + repr(self.value) + ']'

    def __str__(self):
        return self.value

class Expression:
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'Expression[' + repr(self.value) + ']'

    def __str__(self):
        return str(self.value)

class AndConnexive:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __repr__(self):
        return 'AND[' + repr(self.left) + ',' + repr(self.right) + ']'

    def __str__(self):
        return str(self.left) + ' AND ' + str(self.right)

class OrConnexive:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def __repr__(self):
        return 'OR[' + repr(self.left) + ',' + repr(self.right) + ']'

    def __str__(self):
        return str(self.left) + ' OR ' + str(self.right)

class URLPredicate:
    def __init__(self, url):
        self.url = url

    def __repr__(self):
        return 'UrlPredicate[' + repr(self.url) + ']'

    def __str__(self):
        return 'url:' + str(self.url)

class MentionPredicate:
    def __init__(self, user):
        self.user = user

    def __repr__(self):
        return 'MentionPredicate[' + repr(self.user) + ']'

    def __str__(self):
        return '@' + str(self.user)

class HashtagPredicate:
    def __init__(self, hashtag):
        self.hashtag = hashtag

    def __repr__(self):
        return 'HashtagPredicate[' + repr(self.hashtag) + ']'

    def __str__(self):
        return '#' + str(self.hashtag)

class EOFError(Exception):
    pass

class Search:
    def __init__(self, data, debug):
        self.position = 0
        self.data = data
        self.debug = debug

    def expect(self, tokens, token_type):
        try:
            token = tokens.pop(0)
            if isinstance(token, token_type):
                return token
            else:
                raise SyntaxError("Unexpected %s. Expecting %s" % (token, str(token_type)))
        except IndexError:
            raise SyntaxError("Unexpected end of string. Expecting %s" % (str(token_type)))

    def advance(self):
        self.position += 1

        if len(self.data) == self.position:
            self.position = 0
            raise EOFError()

    def lex(self):
        if len(self.data) == 0:
            return []

        tokens = []

        try:
            while True:
                token = self.get_token()
                tokens.append(token)
                self.advance()
        except EOFError:
            pass

        return tokens
            
    def get_token(self):
        char = self.data[self.position]

        if char == ':':
            return ColonToken()
        elif char == '@':
            return MentionToken()
        elif char == '#':
            return HashtagToken()
        elif char == ' ':
            return OrToken()
        elif False and char == '+':
            return AndToken()
        elif False and char == '(':
            return OpeningParenthesesToken()
        elif False and char == ')':
            return ClosingParenthesesToken()
        else:
            return StringCharacterToken(char)

    def parse(self):
        self.debug.append('1. Parsing "%s"' % (self.data,))

        tokens = self.lex()

        self.debug.append('2. Lexed "%s"' % (repr(tokens),))

        # join contiguous streams of StringCharacterToken's
        joined_tokens = []

        skip_to = -1
        for i in range(len(tokens)):
            token = tokens[i]
            if skip_to >= i:
                continue

            if isinstance(token, StringCharacterToken):
                j = i
                string = ""
                while j < len(tokens) and isinstance(tokens[j], StringCharacterToken):
                    string += str(tokens[j])
                    j += 1
                skip_to = j-1
                joined_tokens.append(StringToken(string))
            else:
                joined_tokens.append(token)

        self.debug.append('3. Joined "%s"' % (repr(joined_tokens),))

        parsed_tokens = []

        skip_to = -1
        for i in range(len(joined_tokens)):
            token = joined_tokens[i]
            if skip_to >= i:
                continue

            if isinstance(token, ColonToken) and i > 0 and isinstance(joined_tokens[i-1], StringToken) and joined_tokens[i-1].value == 'url' and i < len(joined_tokens) and isinstance(joined_tokens[i+1], StringToken):
                parsed_tokens.append(URLPredicate(str(joined_tokens[i+1])))
                skip_to = i+1
            elif isinstance(token, HashtagToken) and i < len(joined_tokens) and isinstance(joined_tokens[i+1], StringToken):
                parsed_tokens.append(HashtagPredicate(str(joined_tokens[i+1])))
                skip_to = i+1
            elif isinstance(token, MentionToken) and i < len(joined_tokens) and isinstance(joined_tokens[i+1], StringToken):
                screen_name = str(joined_tokens[i+1])
                user = beta_predicate_users(TUser.query.filter(TUser.screen_name == screen_name)).first()
                if user is not None:
                    parsed_tokens.append(MentionPredicate(str(user.user_id)))
                skip_to = i+1
            else:
                parsed_tokens.append(token)

        self.debug.append('4. First Pass "%s"' % (repr(parsed_tokens),))

        return parsed_tokens
    
    def apply(self, query, tree):
        # for now, tree is just a set of ORs
        ors = []

        for token in tree:
            if isinstance(token, HashtagPredicate):
                ors.append(and_(TweetEntity.type == TweetEntity.TYPE_HASHTAG, TweetEntity.text == token.hashtag))
            elif isinstance(token, MentionPredicate):
                ors.append(and_(TweetEntity.type == TweetEntity.TYPE_MENTION, TweetEntity.text == token.user))
            elif isinstance(token, URLPredicate):
                ors.append(and_(TweetEntity.type == TweetEntity.TYPE_URL, TweetEntity.text == token.url))
            elif isinstance(token, StringToken):
                ors.append(Tweet.text.contains(str(token)))

        return or_(*ors)
