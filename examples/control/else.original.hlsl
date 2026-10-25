Texture2D<float4> tex:register(t0);
SamplerState samp:register(s0);
float4 main(float4 a:COLOR0):SV_Target
{
    bool b=a.x>0.5;
    float4 c;
    if(b) {clip(a.y);c=a;}
    else {c=tex.Sample(samp,a.xy)+ddx(a);}
    return c;
}
