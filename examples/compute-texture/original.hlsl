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

float3 ToneMap(float3 color) {
    float3 positive = max(color, 0.0);
    float3 exposed = positive * Exposure;
    return exposed / (1.0 + exposed);
}

[numthreads(8, 8, 1)]
void main(uint3 threadId : SV_DispatchThreadID) {
    uint2 pixel = threadId.xy;
    if (pixel.x >= Width || pixel.y >= Height) return;
    float4 scene = Scene.Load(int3(pixel, 0));
    float4 bloom = Bloom.Load(int3(pixel, 0));
    float3 mapped = ToneMap(scene.rgb + BloomStrength * bloom.rgb);
    float luminance = dot(mapped, float3(0.25, 0.5, 0.25));
    Color[pixel] = float4(mapped, 1.0);
    Auxiliary[pixel] = float4(saturate(luminance), min(luminance, 1.0), 0.0, 1.0);
}
