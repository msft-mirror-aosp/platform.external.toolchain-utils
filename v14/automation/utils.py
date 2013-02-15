import StringIO
import pickle

def Serialize(argument):
  string = StringIO.StringIO()
  pickle.dump(argument, string)
  return string.getvalue()

def Deserialize(argument):
  return pickle.load(StringIO.StringIO(argument))
