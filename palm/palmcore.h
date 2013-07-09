#ifndef PALMCORE_H
#define PALMCORE_H

typedef enum {
    pbf_type_varint = 0,
    pbf_type_fixed64 = 1,
    pbf_type_length = 2,
    pbf_type_fixed32 = 5
} pbf_field_type;

#define REPEATED_START_SIZE (64)
#define REPEATED_HARD_CAP (64 * 64 * 64 * 64)

typedef struct pbf_mark {
    char exists;
    pbf_field_type ftype;
    union {
        uint64_t i64;
        uint32_t i32;
        struct {
            uint64_t len;
            char *data;
        } s;
    } fdata;
    unsigned char *raw;
    uint64_t raw_len; // copy if nonzero
    unsigned char buf[20]; // for new ints or headers
    unsigned char buf_len; // copy if nonzero
    struct pbf_mark *last;
    struct pbf_mark *next;
    struct pbf_mark *repeats;
    uint32_t repeated_alloc;
    uint32_t repeated_used;
} pbf_mark;

typedef struct pbf_protobuf {
    unsigned char *data;
    uint64_t data_length;
    pbf_mark *marks;
    int num_marks;
    int max_mark;
    int parsed;
} pbf_protobuf;
pbf_protobuf * pbf_load(char *data, uint64_t size, char *stringmap, uint64_t maxstringid);

void pbf_free(pbf_protobuf *pbf);

int pbf_get_bytes(pbf_protobuf *pbf, uint64_t field_num,
    char **out, uint64_t *length);

int pbf_get_integer(pbf_protobuf *pbf, uint64_t field_num, uint64_t *res);

int pbf_get_signed_integer(pbf_protobuf *pbf,
    uint64_t field_num, int64_t *res,
    int32_t *res32, int use_zigzag);
int pbf_exists(pbf_protobuf *pbf, uint64_t field_num);

int pbf_set_bytes(pbf_protobuf *pbf, uint64_t field_num,
        char *out, uint64_t length);

int pbf_set_integer(pbf_protobuf *pbf, uint64_t field_num,
        uint64_t value, int fixed);

int pbf_set_signed_integer(pbf_protobuf *pbf, uint64_t field_num,
        int64_t value, int zigzag);

unsigned char *pbf_serialize(pbf_protobuf *pbf, int *length);

void pbf_remove(pbf_protobuf *pbf, uint64_t field_num);


typedef void(*pbf_byte_stream_callback) (char *, uint64_t length, void *);
typedef void(*pbf_uint_stream_callback) (uint64_t, void *);
typedef void(*pbf_sint_stream_callback) (int64_t, int32_t, void *);

int pbf_get_bytes_stream(pbf_protobuf *pbf, uint64_t field_num,
        pbf_byte_stream_callback cb, void *passthrough);

int pbf_get_integer_stream(pbf_protobuf *pbf, uint64_t field_num, 
        pbf_uint_stream_callback cb, void *passthrough);

int pbf_get_signed_integer_stream(pbf_protobuf *pbf,
        uint64_t field_num, int use_32, int use_zigzag,
        pbf_sint_stream_callback cb, void *passthrough);

#endif /* PALMCORE_H */
