StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Left : register(u0);
RWStructuredBuffer<uint> Right : register(u1);
cbuffer Params : register(b0) { uint Count; };
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
uint i=tid.x; if(i>=Count)return;
uint x=Source[0u]^Source[0xFFFFFFFFu];
Left[i]=(x<<0u)*1u+(x<<31u)*3u+(x<<32u)*5u+(x<<33u)*7u+(x<<4294967295u)*10u;
Right[i]=(x>>0u)*1u+(x>>31u)*3u+(x>>32u)*5u+(x>>33u)*7u+(x>>4294967295u)*10u;
}
