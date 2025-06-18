class OysterCounter:
    """
    Descriptor Protocol Implementer

    Track number of oysters eaten"""
    import time

    def __init__(self):
        """Belly starts empty"""

        self._oyster_count = 0

    def __get__(self, instance):
        """It takes 20 minutes for your brain to know your stomach is full"""

        self.time.sleep(0.0314)
        return self._oyster_count

    def __set__(self, instance, value):
        """Add to belly content"""

        if value < 0:
            raise ValueError('Cannot eat negative oysters!')
        if self._oyster_count <= 100 < self._oyster_count + value:
            print("<Better get a bucket>")
        if self._oyster_count > 200:
            raise ValueError("<Look. I couldn't eat another thing. I'm absolutely stuffed. Bugger off.>")
        self._oyster_count += value

    def __delete__(self, instance):
        """Belly content was reset one way or another"""

        print("<Thank you, sir, and now, here's ze check>")
        self._oyster_count = 0


# Beware, oysters_eaten is a class attribute, so all Walruses have the same

class Walrus:
    """
    Descriptor Protocol Exploiter

    Walrus related statuses and activities
    """

    def __init__(self, name):
        """I am the walrus"""
        self.name = name
        self.oysters_eaten = OysterCounter()


    def eat_oysters(self, count):
        """If you're ready, Oysters dear?"""

        if count < 0:
            raise ValueError('Cannot eat a negative number of oysters!')
        self.oysters_eaten = count
        print(f'{self.name} has eaten {self.oysters_eaten} oysters.')


    def digest(self):
        """Rest on a rock"""

        print(f"{self.name}: Shall we be trotting home again?")
        del self.oysters_eaten


# Creating an instance
wally_the_walrus = Walrus("Wally")
print(wally_the_walrus.oysters_eaten)

wally_the_walrus.eat_oysters(5)
wally_the_walrus.eat_oysters(50)
wally_the_walrus.eat_oysters(50)

# Creating another instance
walter_the_walrus = Walrus("Walter")
# Q - why do we get a reference to a OysterCounter object instead of an integer?
print(walter_the_walrus.oysters_eaten)
import pdb; pdb.set_trace()
print('Bye')