float4 main(float4 input : COLOR0) : SV_Target {
    uint4 x = asuint(input);
    uint4 sum = x;
    x += uint4(1u, 3u, 5u, 7u); sum ^= x;
    x -= 9u; sum += x;
    x *= 3u; sum ^= x;
    x &= 0xFFFFFFF0u; sum += x;
    x |= 5u; sum ^= x;
    x ^= 0x12345678u; sum += x;
    x <<= uint4(0u,31u,32u,63u); sum ^= x;
    x >>= uint4(0u,31u,32u,63u); sum += x;
    sum ^= ~x; sum += -x;
    return asfloat(sum);
}
