StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
uint i=tid.x; if(i>=Count)return; uint h=(Source[i]^Count)+0x9E3779B9u; h=h*0x85EBCA6Bu; h=h^(h>>13u); h=h*0xC2B2AE35u; Output[113u]=h^(h>>16u);
}
