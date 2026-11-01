StructuredBuffer<uint> Source : register(t0);
RWStructuredBuffer<uint> Output : register(u0);
cbuffer Params : register(b0) { uint Count; };
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) {
uint i=tid.x; bool a=i<Count && Source[i]!=0u; bool b=i>=Count || Source[i]==0u; uint c=i<Count?Source[i]:0u; if(i<Count){if(a && !b) Output[i]=c; else Output[i]=c;}
}
