# 🌐 Connect Framework Examples - Modern RPC

Welcome to the Connect framework examples showcasing modern, browser-native RPC that provides a better developer experience than traditional gRPC while maintaining full compatibility.

## 📖 Overview

Connect is the modern successor to traditional gRPC-Web, offering:

- **Browser-native RPC** - Works directly in browsers without complex proxies
- **Full gRPC compatibility** - Seamless interoperability with existing gRPC services  
- **Better developer experience** - Simpler APIs, better error handling, smaller bundles
- **Multi-language support** - Go servers, TypeScript/JavaScript clients
- **Streaming support** - Server streaming, client streaming, and bidirectional streaming

## 🏗️ Examples Structure

- **[fullstack-demo/](./fullstack-demo/)** - Complete Connect-Go server + Connect-ES web client
- **[streaming-example/](./streaming-example/)** - Modern streaming patterns with real-time features
- **[migration-guide/](./migration-guide/)** - Side-by-side gRPC vs Connect comparison

## 🎯 Key Benefits Over Traditional gRPC

### Bundle Size Comparison
```
Traditional gRPC-Web:    ~500KB bundle size
Connect-ES:              ~300KB bundle size  
                         40% smaller bundles
```

### Browser Compatibility
**Traditional gRPC-Web**: Requires gRPC-Web proxy, limited browser features
**Connect**: Native browser support, modern web standards, no proxy needed

### Developer Experience
**Traditional gRPC**: Complex setup, difficult debugging, limited browser dev tools
**Connect**: Simple APIs, excellent debugging, full browser dev tools support

## 🚀 Quick Start

### 1. Full-Stack Demo
```bash
cd fullstack-demo
buck2 run :server &
buck2 run :web_client
```

### 2. Streaming Demo
```bash
cd streaming-example
buck2 run :chat_server &
buck2 run :streaming_client
```

### 3. Migration Comparison
```bash
cd migration-guide
buck2 test :grpc_vs_connect_comparison
```

## 💡 Modern RPC Patterns

### Simple RPC Service
```protobuf
syntax = "proto3";

import "buf/validate/validate.proto";

service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
  rpc CreateUser(CreateUserRequest) returns (CreateUserResponse);
  rpc UpdateUser(UpdateUserRequest) returns (UpdateUserResponse);
}

message GetUserRequest {
  int64 user_id = 1 [(buf.validate.field).int64.gt = 0];
}
```

### Server Streaming
```protobuf
service NotificationService {
  // Server streaming for real-time notifications
  rpc SubscribeNotifications(SubscribeRequest) returns (stream Notification);
}
```

### Bidirectional Streaming
```protobuf
service ChatService {
  // Real-time chat with bidirectional streaming
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}
```

## 🔧 Language-Specific Examples

### Connect-Go Server
```go
package main

import (
    "context"
    "net/http"
    
    "connectrpc.com/connect"
    "golang.org/x/net/http2"
    "golang.org/x/net/http2/h2c"
    
    userv1 "example.com/user/v1"
    "example.com/user/v1/userv1connect"
)

type UserServer struct{}

func (s *UserServer) GetUser(
    ctx context.Context,
    req *connect.Request[userv1.GetUserRequest],
) (*connect.Response[userv1.GetUserResponse], error) {
    // Modern, type-safe request handling
    userID := req.Msg.UserId
    
    // Business logic here
    user := &userv1.User{
        Id:    userID,
        Email: "user@example.com",
        Name:  "John Doe",
    }
    
    return connect.NewResponse(&userv1.GetUserResponse{
        User: user,
    }), nil
}

func main() {
    mux := http.NewServeMux()
    path, handler := userv1connect.NewUserServiceHandler(&UserServer{})
    mux.Handle(path, handler)
    
    // Enable HTTP/2 for better performance
    http.ListenAndServe(":8080", h2c.NewHandler(mux, &http2.Server{}))
}
```

### Connect-ES Client
```typescript
import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { UserService } from "./gen/user/v1/user_service_connect";

// Create transport
const transport = createConnectTransport({
  baseUrl: "http://localhost:8080",
});

// Create client
const client = createClient(UserService, transport);

// Make type-safe RPC calls
async function getUser(userId: bigint) {
  try {
    const response = await client.getUser({ userId });
    console.log("User:", response.user);
    return response.user;
  } catch (error) {
    console.error("RPC failed:", error);
    throw error;
  }
}

// Call the service
getUser(123n);
```

### Browser Streaming
```typescript
// Server streaming example
for await (const notification of client.subscribeNotifications({ userId: 123n })) {
  console.log("New notification:", notification);
  updateUI(notification);
}

// Bidirectional streaming
const chatStream = client.chat();

// Send messages
chatStream.send({ message: "Hello!", userId: 123n });

// Receive messages
for await (const message of chatStream) {
  displayMessage(message);
}
```

## 📊 Migration Guide from gRPC

### Step 1: Update Proto Services (No Changes Needed!)
```protobuf
// Your existing gRPC service definitions work as-is
service UserService {
  rpc GetUser(GetUserRequest) returns (GetUserResponse);
}
```

### Step 2: Update Server Implementation
**Before (gRPC)**:
```go
type server struct {
    pb.UnimplementedUserServiceServer
}

func (s *server) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.GetUserResponse, error) {
    // Implementation
}

func main() {
    lis, _ := net.Listen("tcp", ":50051")
    s := grpc.NewServer()
    pb.RegisterUserServiceServer(s, &server{})
    s.Serve(lis)
}
```

**After (Connect)**:
```go
type UserServer struct{}

func (s *UserServer) GetUser(
    ctx context.Context,
    req *connect.Request[pb.GetUserRequest],
) (*connect.Response[pb.GetUserResponse], error) {
    // Same implementation, better type safety
}

func main() {
    mux := http.NewServeMux()
    path, handler := pbconnect.NewUserServiceHandler(&UserServer{})
    mux.Handle(path, handler)
    http.ListenAndServe(":8080", h2c.NewHandler(mux, &http2.Server{}))
}
```

### Step 3: Update Client Code
**Before (gRPC-Web)**:
```typescript
import { UserServiceClient } from './user_service_grpc_web_pb';
import { GetUserRequest } from './user_service_pb';

const client = new UserServiceClient('http://localhost:8080');
const request = new GetUserRequest();
request.setUserId(123);

client.getUser(request, {}, (err, response) => {
  if (err) {
    console.error(err);
  } else {
    console.log(response.getUser());
  }
});
```

**After (Connect-ES)**:
```typescript
import { createClient } from "@connectrpc/connect";
import { createConnectTransport } from "@connectrpc/connect-web";
import { UserService } from "./user_service_connect";

const client = createClient(UserService, createConnectTransport({
  baseUrl: "http://localhost:8080",
}));

try {
  const response = await client.getUser({ userId: 123n });
  console.log(response.user);
} catch (error) {
  console.error(error);
}
```

## 🧪 Testing Strategy

### Server Testing
```go
func TestUserService(t *testing.T) {
    // Connect makes testing easier with standard HTTP
    server := &UserServer{}
    mux := http.NewServeMux()
    path, handler := userv1connect.NewUserServiceHandler(server)
    mux.Handle(path, handler)
    
    testServer := httptest.NewServer(mux)
    defer testServer.Close()
    
    client := userv1connect.NewUserServiceClient(
        http.DefaultClient,
        testServer.URL,
    )
    
    response, err := client.GetUser(context.Background(), 
        connect.NewRequest(&userv1.GetUserRequest{UserId: 123}))
    assert.NoError(t, err)
    assert.Equal(t, int64(123), response.Msg.User.Id)
}
```

### Client Testing
```typescript
import { createClient } from "@connectrpc/connect";
import { createMockTransport } from "@connectrpc/connect/mock";

// Mock transport for testing
const mockTransport = createMockTransport({
  getUser: (req) => ({
    user: { id: req.userId, name: "Test User" }
  })
});

const client = createClient(UserService, mockTransport);

// Test your client code
const user = await client.getUser({ userId: 123n });
expect(user.name).toBe("Test User");
```

## 🔍 Troubleshooting

### Common Issues

**Issue**: CORS errors in browser
**Solution**: Configure CORS properly on Connect server
```go
corsHandler := cors.New(cors.Options{
    AllowedOrigins: []string{"http://localhost:3000"},
    AllowedMethods: []string{"POST"},
    AllowedHeaders: []string{"Content-Type", "Connect-Protocol-Version"},
}).Handler(handler)
```

**Issue**: Large bundle sizes
**Solution**: Use code splitting and only import needed services
```typescript
// Instead of importing everything
// import { AllServices } from "./gen/all_services";

// Import only what you need
import { UserService } from "./gen/user_service";
```

**Issue**: Streaming not working
**Solution**: Ensure proper HTTP/2 configuration and browser support
```go
// Enable HTTP/2 for streaming
http.ListenAndServe(":8080", h2c.NewHandler(mux, &http2.Server{}))
```

### Best Practices
1. **Use HTTP/2** - Essential for performance and streaming
2. **Enable compression** - Reduces payload sizes significantly
3. **Handle errors gracefully** - Connect provides detailed error information
4. **Use streaming judiciously** - Great for real-time features, but adds complexity

---

**Modern RPC with Connect: Better performance, simpler code, happier developers! 🎉**
