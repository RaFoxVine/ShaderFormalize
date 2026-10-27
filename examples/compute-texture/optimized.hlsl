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

[numthreads(8, 8, 1)]
void main(uint3 threadId : SV_DispatchThreadID) {
    uint2 pixel = threadId.xy;
    if (pixel.x >= Width || pixel.y >= Height) return;
    float4 scene = Scene.Load(int3(pixel, 0));
    float4 bloom = Bloom.Load(int3(pixel, 0));
    float3 exposed = max(scene.rgb + BloomStrength * bloom.rgb, 0.0) * Exposure;
    float3 mapped = exposed / (exposed + 1.0);
    float luminance = mapped.r * 0.25 + mapped.g * 0.5 + mapped.b * 0.25;
    Auxiliary[pixel] = float4(min(max(luminance, 0.0), 1.0), min(luminance, 1.0), 0.0, 1.0);
    Color[pixel] = float4(mapped, 1.0);
}
