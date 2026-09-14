using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

var baseAddress = args.Length > 0 ? args[0] : "http://127.0.0.1:8000";
using var client = new HttpClient { BaseAddress = new Uri(baseAddress) };
using var cancellation = new CancellationTokenSource(TimeSpan.FromSeconds(30));

var request = new ExecuteRequest(
    "dotnet-rest-1",
    "example-agent",
    new AgentInput("Responda pelo cliente .NET."));

var response = await client.PostAsJsonAsync(
    "/v1/executions", request, cancellation.Token);
response.EnsureSuccessStatusCode();
var result = await response.Content.ReadFromJsonAsync<ExecuteResponse>(
    cancellation.Token);
Console.WriteLine($"Execução: {result?.Status}");

using var streamRequest = new HttpRequestMessage(HttpMethod.Post, "/v1/executions/stream")
{
    Content = JsonContent.Create(request),
};
using var streamResponse = await client.SendAsync(
    streamRequest,
    HttpCompletionOption.ResponseHeadersRead,
    cancellation.Token);
streamResponse.EnsureSuccessStatusCode();
await using var body = await streamResponse.Content.ReadAsStreamAsync(cancellation.Token);
using var reader = new StreamReader(body, Encoding.UTF8);
while (await reader.ReadLineAsync(cancellation.Token) is { } line)
{
    if (line.StartsWith("data: ", StringComparison.Ordinal))
    {
        Console.WriteLine($"Evento SSE: {line[6..]}");
    }
}

if (result?.Suspension is { } suspension)
{
    var resume = new ResumeRequest(
        "dotnet-rest-resume-1",
        "example-agent",
        suspension.ResumeToken,
        suspension.ApprovalRequest.ApprovalRequestId,
        "approve",
        DateTimeOffset.UtcNow);
    var resumed = await client.PostAsJsonAsync(
        "/v1/executions/resume", resume, cancellation.Token);
    resumed.EnsureSuccessStatusCode();
    Console.WriteLine("Execução retomada pelo corpo da requisição.");
}

internal sealed record AgentInput(string Message);

internal sealed record ExecuteRequest(
    [property: JsonPropertyName("request_id")] string RequestId,
    [property: JsonPropertyName("agent_id")] string AgentId,
    AgentInput Input);

internal sealed record ApprovalRequest(
    [property: JsonPropertyName("approval_request_id")] string ApprovalRequestId);

internal sealed record Suspension(
    [property: JsonPropertyName("resume_token")] string ResumeToken,
    [property: JsonPropertyName("approval_request")] ApprovalRequest ApprovalRequest);

internal sealed record ExecuteResponse(string Status, Suspension? Suspension);

internal sealed record ResumeRequest(
    [property: JsonPropertyName("request_id")] string RequestId,
    [property: JsonPropertyName("agent_id")] string AgentId,
    [property: JsonPropertyName("resume_token")] string ResumeToken,
    [property: JsonPropertyName("approval_request_id")] string ApprovalRequestId,
    string Decision,
    [property: JsonPropertyName("decided_at")] DateTimeOffset DecidedAt);
