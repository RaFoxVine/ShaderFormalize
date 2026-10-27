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
void main(uint3 threadId : SV_DispatchThreadID) {
    uint2 pixel=threadId.xy;
    if(pixel.x>=Width || pixel.y>=Height)return;
    float4 value=Scene.Load(int3(pixel,0))*2.0+1.0;
    Auxiliary[pixel]=value;
    Color[pixel]=value;
}
