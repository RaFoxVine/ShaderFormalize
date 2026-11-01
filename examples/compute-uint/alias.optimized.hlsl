StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
uint i=tid.x; if(i>=Count)return;
uint x=Source[i]; Output[i]=(x+1u)^Count;
}
