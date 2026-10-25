Texture2D<float4> tex:register(t0);
SamplerState samp:register(s0);
float4 main(float4 a:COLOR0):SV_Target
{
    bool b=a.x>0.5;
    if(b) {clip(a.y);return a;}
    return tex.Sample(samp,a.xy)+ddx(a);
}
