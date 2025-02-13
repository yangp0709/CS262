# Comparison Between JSON and Custom Protocol:

In both JSON and custom protocol implementations, each client creates a new thread, which runs in the background, allowing support with many clients at once. Thus in terms of scalability, both programs should theoretically be able to support many clients. 

However, there are significant differences in efficiency between the two implementations. In the JSON implementation, it sends information from the client to the server as a JSON object, and it converts the response from the server to the client into a JSON object. Meanwhile, the custom wire protocol sends and receives information in binary format. Thus, the JSON implementation is less inefficient in terms of time and message size sent back and forth between the client and server due to the overhead of dealing with JSON objects instead of the raw binary formats. We can see this through empirical experiments. 

The figures below show the results of an experiment where we sent messages of $n$ characters 10 times and averaged the results over those 10 trials for each $n$. 
1) We can see in Figure 1 that the size of the message sent from the client to the server is larger for the JSON implementation than the custom implementation because sending a message as a JSON object adds additional space compared to the binary format. We can also see that for both implementations, the message size linearly increases as the character count increases in the message, which is as expected.
2) We can see in Figure 2 that the size of the response sent from the server to the client is larger for the JSON implementation than the custom implementation because for the JSON implementation, the response has to be in a format that can be converted into a JSON object, while that is not necessary for the custom implementation. For both implementations, the response size is static as the character count increases because the response from the server in both implementations is independent of the character count, meaning the server does not send back the original message; thus, the response message size is always the same, independent of the original message size.
3) We can see in Figure 3 that the time taken to send a message is significantly faster with the custom implementation compared to the JSON implementation. While the time taken increases linearly with the character count using the JSON implementation, there is seemingly no increase in time taken in the custom implementation. If we look at Figure 4, which only shows the time taken for the custom implementation, we can see that there are fluctuations and some slight increase in time as the character count increases, but we can clearly see from Figure 3 that the custom implementation is far more efficient than the JSON implementation in terms of time. 

Figure 1:
![](experiment/message_size_plot.png)

Figure 2:
![](experiment/response_size_plot.png)

Figure 3:
![](experiment/time_taken_plot.png)

Figure 4:
![](experiment/time_taken_custom_only_plot.png)
