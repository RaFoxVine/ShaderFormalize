groupshared float4 Shared[2];
StructuredBuffer<float4> Input : register(t0);
RWStructuredBuffer<float4> Output : register(u0);

[numthreads(2, 1, 1)]
void main(uint3 tid : SV_GroupThreadID)
{
    uint i = tid.x;
    Shared[i] = Input[i];
    GroupMemoryBarrierWithGroupSync();
    Output[i] = Shared[1u - i];
}
