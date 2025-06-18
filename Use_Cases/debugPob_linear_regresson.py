from sklearn.linear_model import LinearRegression

import pdb; pdb.set_trace()
# Sample data
X = [[1], [2], [3], [4], [5]]  # Feature: hours studied
y = [2, 4, 6, 8, 10]           # Target: exam scores

# Initialize and train the model
model = LinearRegression()
model.fit(X, y)

# Make a prediction
predicted = model.predict([[6]])  # Predict score for 6 hours studied
print(predicted)  # Output: [12.]