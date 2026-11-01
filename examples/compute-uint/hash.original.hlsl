StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
uint Hash(uint x) { uint h = (x ^ Count) + 0x9E3779B9u; h *= 0x85EBCA6Bu; h ^= h >> 13u; h *= 0xC2B2AE35u; return h ^ (h >> 16u); }
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
uint i=tid.x; if(i>=Count)return; Output[i+0xFFFFFFFFu+1u]=Hash(Source[i]);
}
