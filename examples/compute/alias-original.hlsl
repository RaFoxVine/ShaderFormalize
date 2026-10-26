StructuredBuffer<float4> SourceA : register(t0);
StructuredBuffer<float4> SourceB : register(t1);
RWStructuredBuffer<float4> Sum : register(u0);
RWStructuredBuffer<float4> Difference : register(u1);
cbuffer Parameters : register(b0) { uint Count; };

[numthreads(8, 1, 1)]
void main(uint3 threadId : SV_DispatchThreadID)
{
    uint index = threadId.x;
    if (index >= Count) return;
    float4 a = SourceA[index];
    float4 b = SourceB[index];
    Sum[index] = a + b;
    Sum[index] = SourceA[index] * 2.0;
    Difference[index] = SourceA[index] - b;
}
