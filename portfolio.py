a=input("Enter your first number:")
oprator=input("Enter your oprator :/,*,%,-,+")
b=input("Enter your second number:")
a=int(a)
b=int(b)
if oprator=="-":
 print(a-b)
elif oprator=="+":
 print(a+b)
elif oprator=="*":
 print(a*b)
elif oprator=="/":
    try:
        print(a/b)
    except:   
        print("Invalid statment")
elif oprator=="%":
  print(a%b)
else:
 print("Invalid oprator")