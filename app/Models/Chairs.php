<?php

namespace App\Models;

use Carbon\Traits\Date;
use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Chairs extends Model
{
    use HasFactory;

    protected $table = 'bus_empty_chairs';
    protected $casts = [
        'chairs' => "array",
    ];

    public function weekly_schedule() {
        return $this->belongsTo(WeeklySchedule::class);
    }

    /**
     * @OA\Property(
     *     title="ID",
     *     description="ID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private $id;

    /**
     * @OA\Property(
     *     title="ID",
     *     description="ID",
     *     format="int64",
     *     example=1
     * )
     *
     * @var integer
     */
    private $ws_id;

    /**
     * @OA\Property(
     *     title="Chairs",
     *     description="array of chairs are empty",
     *     format="array",
     *     example=1
     * )
     *
     * @var array
     */
    private $chairs;

    /**
     * @OA\Property(
     *     title="date",
     *     description="date of teravelling",
     *     format="date",
     *     example=1
     * )
     *
     * @var Date
     */
    private $date;

}
