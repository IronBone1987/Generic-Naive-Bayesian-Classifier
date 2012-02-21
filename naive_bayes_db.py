import sqlite3 as sl3
from os.path import exists

class NaiveBayesDB(object):
    """Creates and maintains a database that will 
    hold values for the NaiveBayesClassifier.
    TODO: 
    - try/execpt database creation or read/write error; test using os.stat
    - if file exists, test for permissions to read/write, also check size
    """
    def __init__(self,
                 database_path,
                 global_description='',
                 positive_description='',
                 negative_description=''):
        """Creates the database schema if the file does not exist"""
        if not exists(database_path):
            self.db_connection = sl3.connect(database_path)        
            cursor = self.db_connection.cursor()
            cursor.execute("create table counters (counter INTEGER, name TEXT, description TEXT)")
            cursor.execute("insert into counters VALUES (0, 'global_counter', ?)", (global_description,))
            cursor.execute("insert into counters VALUES (0, 'positive_counter', ?)", (positive_description,))
            cursor.execute("insert into counters VALUES (0, 'negative_counter', ?)", (negative_description,))
            cursor.execute("create table negative_classification (token TEXT UNIQUE, count INTEGER)")
            cursor.execute("create table positive_classification (token TEXT UNIQUE, count INTEGER)")
            self.db_connection.commit()
            cursor.close()
        self.db_connection = sl3.connect(database_path)
    
    def update_counter(self, counter='', value=0):
        """Increment each counter according to train methods."""
        possible_counters = ['global_counter', 'positive_counter', 'negative_counter']
        if (not counter) or (counter not in possible_counters):
            return False
        cursor = self.db_connection.cursor()
        current = cursor.execute("SELECT counter from counters WHERE name=?", (counter,))
        if current == 0:
            return False
        current_value = current.fetchone()[0]
        current_value += value
        cursor.execute("UPDATE counters SET counter=? WHERE name=?", (current_value, counter))
        return True

    # TODO: execute many
    def _increment_or_insert(self, token, polarity=None):
        """for each token, if token not in database, add token to the database and set count to 1; if the
        token exists in the database, increment the counter by 1."""
        if not polarity:
            return False
        cursor = self.db_connection.cursor()
        try:
            if polarity == 'positive':
                cursor.execute("insert into positive_classification VALUES (?, ?)", (token, 1))
            elif polarity == 'negative':
                cursor.execute("insert into negative_classification VALUES (?, ?)", (token, 1))
        except sl3.IntegrityError: # token exists in database, so increment token count
            if polarity == 'positive':
                current = cursor.execute("SELECT count from positive_classification WHERE token=?", (token,))
                value = current.fetchone()[0]
                value += 1
                cursor.execute("UPDATE positive_classification SET count=? WHERE token=?", (value, token))
            elif polarity == 'negative':
                current = cursor.execute("SELECT count from negative_classification WHERE token=?", (token,))
                value = current.fetchone()[0]
                value += 1
                cursor.execute("UPDATE negative_classification SET count=? WHERE token=?", (value, token))
        finally:
            self.db_connection.commit()
            cursor.close()
        return None

    def _decrement_or_remove(self, token, polarity):
        """for each token, if token not in database, pass, else if token count >
        1, decrement, else if token count == 1, remove element from database"""
        if (not polarity) or (polarity not in ['positive', 'negative']):
            return False
        cursor = self.db_connection.cursor()
        try:
            if polarity == 'positive':
                current_cursor = cursor.execute("SELECT count from positive_classification WHERE token=?", (token,))
                # current_cursor 
                current_value = current_cursor.fetchone()
                if not current_value: # not in database; do nothing
                    return True
                value = current_value[0]
                if value == 1: # remove the token from the database instead of setting to 0
                    cursor.execute("DELETE FROM positive_classification WHERE token=?", (token,))
                else: # decrement
                    value -= 1
                    cursor.execute("UPDATE positive_classification SET count=? WHERE token=?", (value, token))
            else:
                current_cursor = cursor.execute("SELECT count from negative_classification WHERE token=?", (token,))
                current_value = current_cursor.fetchone()
                if not current_value: # not in database; do nothing
                    return True
                value = current_value[0]
                if value == 1: # remove the token from the database instead of setting to 0
                    cursor.execute("DELETE FROM negative_classification WHERE token=?", (token,))
                else: # decrement
                    value -= 1
                    cursor.execute("UPDATE negative_classification SET count=? WHERE token=?", (value, token))
        finally:
            self.db_connection.commit()
            cursor.close()
        return None

    # TODO: execute many
    def train_positive(self, tokens):
        """batch update/insert tokens and increment global and positive counters"""
        for token in tokens:
            self._increment_or_insert(token, polarity='positive')
        self.update_counter('global_counter', value=1)
        self.update_counter('positive_counter', value=1)
        return None

    def train_negative(self, tokens):
        """For each token in tokens, add token/counter and/or increment negative_counter in database.
        Increment the global counter"""
        for token in tokens:
            self._increment_or_insert(token, polarity='negative')
        self.update_counter('global_counter', value=1)
        self.update_counter('negative_counter', value=1)
        return None
    
    def untrain_positive(self, tokens):
        """for each token, if token in database, decrement the token's counter by 1.
        if token does not exist in the database, pass; if token count == 1, 
        remove from database"""
        for token in tokens:
            self._decrement_or_remove(token, polarity='positive')
        self.update_counter('global_counter', value=-1)
        self.update_counter('positive_counter', value=-1)
        return None                

    def untrain_negative(self, tokens):
        """for each token, if token in database, decrement the token's counter by 1.
        if token does not exist in the database, pass; if token count == 1, 
        remove from database"""
        for token in tokens:
            self._decrement_or_remove(token, polarity='negative')
        self.update_counter('global_counter', value=-1)
        self.update_counter('negative_counter', value=-1)
        return None

    def counter_for_token(self, token, polarity=''):
        if (not polarity) or (polarity not in ['positive', 'negative']):
            return False
        cursor = self.db_connection.cursor()
        try:
            if polarity == 'positive':
                current = cursor.execute("SELECT count from positive_classification WHERE token=?", (token,))
                current_value = current_cursor.fetchone()
                if not current_value: # not in database
                    current_value = .5 # using this value as a default; TODO: find optimal value
                else:
                    current_value = current_value[0]
                return current_value
            else:
                current = cursor.execute("SELECT count from negative_classification WHERE token=?", (token,))
                current_value = current_cursor.fetchone()
                if not current_value: # not in database; use .5
                    # don't divide by zero
                    current_value = 1 # using this value as a default; TODO: find optimal value
                else:
                    current_value = current_value[0]
                return current_value
        finally:
            cursor.close()
        return True

    def total_for_polarity(self, polarity=''):
        if (not polarity) or (polarity not in ['positive', 'negative']):
            return False
        cursor = self.db_connection.cursor()
        current_counter = cursor.execute("SELECT counter from counters WHERE name=?", (polarity,))
        counter_value = current_counter.fetchone()[0]
        if counter_value == 0:
            counter_value = 1
        return counter_value
        
        
    # def test_token(self, token):
    #     """Accepts: a Token object; Returns: the token with
    #     the probability of it occuring in each of the positive and negative
    #     databases"""
    #     if not polarity:
    #         return False
    #     current = self.db_connection.cursor()
    #     if polarity == 'positive':
    #         current = cursor.execute("SELECT count from positive_classification WHERE token=?", (token,))
    #         current_counter = cursor.execute("SELECT counter from counters WHERE name=?", ('positive_counter',))
    #         counter_value = current_counter.fetchone()[0]
    #         current_value = current_cursor.fetchone()
    #         if not current_value: # not in database; use 1 as value
    #             current_value = 1 # using this value as a default; TODO: discover other methods
    #         else:
    #             current_value = current_value[0]
    #         positive_association = current_value/counter_value
    #         negative_association = 
    #         token.positive_value = 

    #     if polarity == 'negative':
    #         current = cursor.execute("SELECT count from negative_classification WHERE token=?", (token,))
    #         current_counter = cursor.execute("SELECT counter from counters WHERE name=?", ('negative_counter',))
    #         counter_value = current_counter.fetchone()[0]
    #         current_value = current_cursor.fetchone()
    #         if not current_value: # not in database; use 1 as value
    #             current_value = 1 # using this value as a default; TODO: discover other methods
    #         else:
    #             current_value = current_value[0]
            
    #         token.negative_value = current_value/counter_value

        
