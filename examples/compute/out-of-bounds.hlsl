StructuredBuffer<float4> SourceA : register(t0);
StructuredBuffer<float4> SourceB : register(t1);
RWStructuredBuffer<float4> Sum : register(u0);
RWStructuredBuffer<float4> Difference : register(u1);
cbuffer Parameters : register(b0) { uint Count; };

[numthreads(8, 1, 1)]
void main(uint3 threadId : SV_DispatchThreadID)
{
    uint index = threadId.x + 0u;
    if (index < Count) {
        float4 a = SourceA.Load(index);
        float4 b = SourceB[index];
        Difference[index] = a + (-b);
        Sum[index+1u] = a * 0.5 + b * 0.5;
    }
}
