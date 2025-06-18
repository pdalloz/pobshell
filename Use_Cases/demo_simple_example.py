class MyUsefulClass:
	"""Very useful indeed"""
	def __init__(self):
		self.monty_quote = "And now for something completely different"

	def square_it(self, x):
		"""Square the argument, then return 42"""
		y = x**2		
		return 42

my_instance = MyUsefulClass()
print(my_instance.monty_quote)
import pobshell; pobshell.shell()
print(my_instance.square_it(42))
