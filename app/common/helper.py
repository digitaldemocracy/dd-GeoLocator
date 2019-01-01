#contains helper functions
def validate_client(client_ip, allowed_ip):
    print "client_ip",client_ip
    return (client_ip in allowed_ip and allowed_ip[client_ip] == 1)
