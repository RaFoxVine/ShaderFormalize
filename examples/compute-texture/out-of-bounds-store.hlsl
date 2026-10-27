Texture2D<float4> Scene : register(t0);
Texture2D<float4> Bloom : register(t1);
RWTexture2D<float4> Color : register(u0);
RWTexture2D<float4> Auxiliary : register(u1);
cbuffer Parameters : register(b0) {
    uint Width;
    uint Height;
    float Exposure;
    float BloomStrength;
};


[numthreads(8,8,1)]
void main(uint3 threadId : SV_DispatchThreadID){
 if(threadId.x!=0u || threadId.y!=0u)return;
 Color[uint2(17u,0u)]=float4(1.0,1.0,1.0,1.0);
}
