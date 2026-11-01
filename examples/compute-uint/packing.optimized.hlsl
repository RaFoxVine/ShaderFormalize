StructuredBuffer<uint> Src0 : register(t0);
StructuredBuffer<uint> Src1 : register(t1);
StructuredBuffer<uint> Src2 : register(t2);
StructuredBuffer<uint> Src3 : register(t3);
RWStructuredBuffer<uint> Packed : register(u0);
RWStructuredBuffer<uint> Dec0 : register(u1);
RWStructuredBuffer<uint> Dec1 : register(u2);
RWStructuredBuffer<uint> Dec2 : register(u3);
RWStructuredBuffer<uint> Dec3 : register(u4);
cbuffer Params : register(b0) { uint Count; };
[numthreads(64,1,1)]
void main(uint3 tid : SV_DispatchThreadID) { uint i=tid.x; if(i>=Count)return;
uint x0=Src0[i];
uint x1=Src1[i];
uint x2=Src2[i];
uint x3=Src3[i];
uint word=(x0&255u)|((x1&255u)<<8u)|((x2&255u)<<16u)|((x3&255u)<<24u);
Packed[i]=word;
Dec0[i]=x0&255u;
Dec1[i]=x1&255u;
Dec2[i]=x2&255u;
Dec3[i]=x3&255u;
}
