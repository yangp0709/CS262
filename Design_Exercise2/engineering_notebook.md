# Chat Application – Comparing gRPC vs. Custom JSON over Sockets

Code Link: https://github.com/yangp0709/CS262/tree/main
---

## 1. Does using gRPC make the application easier or more difficult?

### gRPC Approach

**Pros**

- **Automatic code generation**: After defining the `.proto` file, gRPC auto-generates client and server stubs in multiple languages. This reduces the amount of boilerplate code needed for networking, serialization, deserialization, etc.
- **Built-in streaming & asynchronous features**: Streaming endpoints (e.g., the `Subscribe` method) become straightforward—simply implement a generator on the server side and iterate over the stream on the client side.
- **Structured data**: The `.proto` files enforce strongly typed request/response objects, making it clear which fields exist and how they are typed.
- **Improved error handling**: You can return gRPC status codes like `NOT_FOUND`, `INVALID_ARGUMENT`, and so on, simplifying error logic.

**Cons**

- **Learning curve**: Must understand `.proto` files, the gRPC code-generation workflow, etc. It adds steps compared to a minimalistic setup.
- **Additional tooling**: Requires installing and configuring `protobuf` libraries (`grpcio`, `grpcio-tools`), and regenerating stubs upon changes.

### Custom Wire Protocol Approach

**Pros**

- **Complete control**: You have direct access to every byte in the network protocol. Good if you need a very specialized setup or want minimal dependencies.
- **Minimal external libraries**: Uses only Python’s standard `socket` and `json` modules—no need to install protobuf.

**Cons**

- **More boilerplate**: You must define and maintain your own protocol for message framing, handle partial reads or multiple messages in a buffer, parse raw data, etc.
- **Less clarity**: Without a formal IDL (like `.proto`), client and server can more easily drift out of sync regarding expected message structures.

**Bottom Line**  
For maintainability and rapid development, gRPC typically simplifies many tasks once you’ve learned it. However, raw sockets can be fine for smaller or more specialized needs and remove dependency overhead. Overall, we found that gRPC made our application easier to develop and maintain.

---

## 2. What does it do to the size of the data passed?

### gRPC

- **Protobuf (binary)**: Usually more compact than JSON.  
- Includes an HTTP/2 transport layer, which adds some overhead, but the binary encoding is typically more efficient in terms of payload size.

### Custom JSON

- **Text-based**: Tends to be more verbose than Protobuf, increasing payload sizes slightly.  
- Raw sockets, however, skip some overhead from HTTP/2 frames that gRPC needs. Still, overall JSON typically is larger on average than a Protobuf-encoded payload.

**Summary**  
Protobuf is often smaller and faster, while JSON is easier for humans to read and debug. For a basic chat app, both approaches are probably "fast enough," but gRPC can be more efficient at scale.

---

## 3. How does it change the structure of the client and the server?

### Server Structure

- **gRPC Server**  
  - Implement a class that extends the generated `ChatServiceServicer`.  
  - Define each RPC method (e.g., `Login`, `SendMessage`, etc.) to match the `.proto` definitions.  
  - Concurrency is handled via gRPC’s `ThreadPoolExecutor` or equivalent.  
  - Streaming methods return a generator that yields messages (e.g., for `Subscribe`).

- **Custom Wire Protocol Server**  
  - Manually accept connections (`socket.accept()` in a loop).  
  - Spawn a thread per connection.  
  - Define your own message types and parse JSON payloads.  
  - Subscription/real-time updates require your own concurrency management and possibly custom data structures.

### Client Structure

- **gRPC Client**  
  - Create a `Stub` using auto-generated code from the `.proto` file.  
  - Each server method is simply a function call on the stub.  
  - Streaming calls are iterated over in a loop (e.g., `for msg in stub.Subscribe(...)`).

- **Custom Wire Protocol Client**  
  - Manually connect to the server via a socket.  
  - Send JSON objects that contain a “type” field or a numeric type ID.  
  - Maintain subscription loops, parse incoming JSON messages, etc.

**In short**: The gRPC version organizes each action as an RPC call with typed messages, whereas the raw-socket version does a lot more manual parsing, message dispatch, etc.

---

## 4. How does this change the testing of the application?

### gRPC Testing

- **Unit Tests**: Can directly instantiate or mock the stub and test each RPC with typed requests.  
- **Integration Tests**: Spin up a gRPC server in a test thread and call it using the generated stub.  
- **More structured**: Using strongly typed Protobuf messages also helps ensure you test each field properly.

### Custom Wire Protocol Testing

- **Unit Tests**: Test the individual handler functions using pre-constructed JSON.  
- **Integration Tests**: Must create a client socket, connect to the test server, send the correct JSON, etc.  
- **More manual**: You might need to handle partial reads/writes or re-check that your message framing logic is correct.

---

## Conclusion

1. **Easier or More Difficult?**  
   - gRPC is generally easier to extend, more structured, and reduces the manual “boilerplate” of networking logic.
2. **Data Size**  
   - gRPC uses Protobuf, which is more compact than JSON, though HTTP/2 adds overhead. Overall, Protobuf is more efficient than plain JSON.  
3. **Structure Changes**:  
   - gRPC neatly packages your RPCs as functions and organizes your server as a generated service class.  
   - With raw sockets, you manually parse each incoming message, route it, and manage concurrency.  
4. **Testing**:  
   - gRPC tests can call the stub like normal function calls, leveraging typed request/response objects.  
   - Raw socket tests require custom framing, more manual mocking of socket behavior, or direct socket operations.

Overall, gRPC’s structured approach and built-in streaming capabilities can significantly reduce complexity compared to a custom JSON protocol, particularly for larger, evolving applications.
