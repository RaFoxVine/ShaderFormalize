StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
bool InRange(uint i) { return i<Count; }
uint Identity(uint x) { return x; }
[numthreads(1,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
    uint i=tid.x;
    uint v=(InRange(i)?Identity(Source[i]):0u)^Identity(Source[113u]);
    Output[i]=v;
}
