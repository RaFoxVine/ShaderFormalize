StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
bool InRange(uint i) { return i<Count; }
uint Identity(uint x) { return x; }
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
    uint i=tid.x;
    bool a=(InRange(i) && Source[i]!=0u) || (i>=Count || Identity(Source[i])==0u);
    uint b=InRange(i)?(a?Identity(Source[i]):Identity(Source[i])):0u;
    if(i<Count) Output[i]=b;
}
