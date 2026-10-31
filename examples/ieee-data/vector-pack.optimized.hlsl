struct Packet { uint2 pair; uint3 triple; };
uint2 arrange(uint2 v, uint z) {
    uint2 r;
    if (z < 0x80000000u) { r.x = v.y; } else { r.x = v.x; }
    r.y = v.x ^ z;
    return r;
}
float4 main(float4 input : COLOR0) : SV_Target {
    uint4 x = asuint(input);
    Packet p;
    p.pair = uint2(x.x, x.y);
    p.triple = asuint(asfloat(uint3(p.pair, x.z)));
    Packet q = p;
    uint2 r = arrange(q.triple.xy, x.w);
    uint4 y = uint4(r.x + 3u, r.y + 3u, x.w + 3u, q.triple.z + 3u);
    return asfloat(y);
}
