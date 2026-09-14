using Atlas.Agent.V1;
using Google.Protobuf.WellKnownTypes;
using Grpc.Core;
using Grpc.Net.Client;

var address = args.Length > 0 ? args[0] : "http://127.0.0.1:50051";
using var channel = GrpcChannel.ForAddress(address);
var client = new AgentExecutionService.AgentExecutionServiceClient(channel);
using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(30));
var deadline = DateTime.UtcNow.AddSeconds(20);

var request = new ExecuteRequest
{
    RequestId = "dotnet-grpc-1",
    AgentId = "example-agent",
    Input = new AgentInput { Message = "Responda pelo cliente gRPC .NET." },
};
var response = await client.ExecuteAsync(
    request,
    deadline: deadline,
    cancellationToken: cancellation.Token);
Console.WriteLine($"Execução: {response.Status}");

using var stream = client.Stream(
    request,
    deadline: deadline,
    cancellationToken: cancellation.Token);
await foreach (var item in stream.ResponseStream.ReadAllAsync(cancellation.Token))
{
    Console.WriteLine($"Evento gRPC: {item.Type}");
}

if (response.Suspension is { } suspension)
{
    var resumed = await client.ResumeAsync(
        new ResumeRequest
        {
            RequestId = "dotnet-grpc-resume-1",
            AgentId = "example-agent",
            ResumeToken = suspension.ResumeToken,
            ApprovalRequestId = suspension.ApprovalRequest.ApprovalRequestId,
            Decision = ApprovalDecision.Approve,
            DecidedAt = Timestamp.FromDateTime(DateTime.UtcNow),
        },
        deadline: DateTime.UtcNow.AddSeconds(20),
        cancellationToken: cancellation.Token);
    Console.WriteLine($"Retomada: {resumed.Status}");
}
