<?php

namespace App\Http\Controllers\API;

use App\Enums\Status;
use App\Enums\StatusCode;
use App\Http\Controllers\Controller;
use App\Http\Requests\ListWeeklyScheduleRequest;
use App\Http\Requests\StoreWeeklyScheduleRequest;
use App\Models\WeeklySchedule;
use Illuminate\Http\JsonResponse;
use Symfony\Component\HttpFoundation\Response;

class WeeklyScheduleController extends Controller
{
    /**
     * @OA\Get(
     *      path="/index",
     *      operationId="getlistItems",
     *      tags={"weekly-schedule"},
     *      summary="Get list of source, destination or terminals ",
     *      description="Returns list of source, destination or terminals",
     *      @OA\Parameter(
     *          description="action of oprations each of ['terminals', 'destination', 'source']",
     *          in="path",
     *          name="action",
     *          required=true,
     *          @OA\Schema(type="string"),
     *      ),
     *     @OA\Parameter(
     *          description="city destination short-code with max 5 char",
     *          in="path",
     *          name="destination",
     *          required=true,
     *          @OA\Schema(type="string"),
     *
     *      ),
     *     @OA\Parameter(
     *          description="source city short-code with max 5 char",
     *          in="path",
     *          name="source",
     *          required=true,
     *          @OA\Schema(type="string"),
     *      ),
     *      @OA\Response(
     *          response=200,
     *          description="Successful operation",
     *       ),
     *      @OA\Response(
     *          response=404,
     *          description="Not Found",
     *      )
     *)
     */
    public function index(ListWeeklyScheduleRequest $request): JsonResponse
    {
        $data = null;
        if($request->validated()){
            switch ($request->input("action")){
                case "terminals":
                    $data = WeeklySchedule::groupBy("source_city_id")->get("source_city_id");
                    break;
                case "destination":
                    $validated = $request->validate([
                        'destination' => 'required|string|max:5',
                    ],[
                        'destination.required' => 'destination must be required and lower than 5 char.'
                    ]);
                    if ($validated)
                        $data = WeeklySchedule::where("destination_city_id", "=", $request->input("destination"))->get("source_city_id");
                    else
                        return response()->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, $data=>null])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    break;
                case "source":
                    $validated = $request->validate([
                        'source' => 'required|string|max:5',
                    ],[
                        'source.required' => 'destination must be required and lower than 5 char.'
                    ]);
                    if ($validated)
                        $data = WeeklySchedule::where("source_city_id","=",$request->input("source"))->get("source_city_id", "source_terminal_id");
                    else
                        return response()
                            ->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> null])
                            ->setStatusCode(Response::HTTP_BAD_REQUEST)
                            ->header('Content-Type', 'application/json');
                    break;
            }
            if ($data == null)
                return  response()->json(['status' => Status::Failed , "code" => StatusCode::Failed, "data" => $data])
                    ->header('Content-Type', 'application/json');
            else
                return response() ->json(['status' => Status::Success , "code" => StatusCode::Success, "data"=> $data])
                    ->header('Content-Type', 'application/json');
        }else{
            return  response()->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }

    /**
     * @OA\Post(
     *     path="/weekly-schedule",
     *     summary="Adds a new weekly schedule",
     *     operationId="addweeklyschedule",
     *     tags={"weekly-schedule"},
     *     @OA\Parameter(
     *          description="city source short-code with max 5 char",
     *          in="path",
     *          name="source_city_id",
     *          required=true,
     *          @OA\Schema(type="string"),
     *
     *     ),
     *     @OA\Parameter(
     *          description="source terminal short-code with max 5 char",
     *          in="path",
     *          name="source_terminal_id",
     *          required=true,
     *          @OA\Schema(type="string"),
     *     ),
     *     @OA\Parameter(
     *          description="destination city short-code with max 5 char",
     *          in="path",
     *          name="destination_city_id",
     *          required=true,
     *          @OA\Schema(type="string"),
     *     ),
     *     @OA\Parameter(
     *          description="destination terminal short-code with max 5 char",
     *          in="path",
     *          name="destination_terminal_id",
     *          required=true,
     *          @OA\Schema(type="string"),
     *     ),
     *     @OA\Parameter(
     *          description="day number start from 0",
     *          in="path",
     *          name="moving_day_number",
     *          required=true,
     *          @OA\Schema(type="integer"),
     *          @OA\Examples(example="int", value="0", summary="An int value."),
     *     ),
     *     @OA\Parameter(
     *          description="integer starting taravell by second.",
     *          in="path",
     *          name="moving_time_seconds",
     *          required=true,
     *          @OA\Schema(type="integer"),
     *          @OA\Examples(example="int", value="1", summary="An int value."),
     *     ),
     *     @OA\Parameter(
     *         description="integer travell destance by minuts.",
     *         in="path",
     *         name="traveling_time",
     *         required=true,
     *         @OA\Schema(type="integer"),
     *         @OA\Examples(example="int", value="1", summary="An int value."),
     *     ),
     *     @OA\Parameter(
     *         description="integer capacity of bus.",
     *         in="path",
     *         name="capacity",
     *         required=true,
     *         @OA\Schema(type="integer"),
     *         @OA\Examples(example="int", value="1", summary="An int value."),
     *     ),
     *     @OA\Parameter(
     *         description="integer type of bus",
     *         in="path",
     *         name="bus_type",
     *         required=true,
     *         @OA\Schema(type="integer"),
     *     ),
     *     @OA\Parameter(
     *         description="price of each bus chair",
     *         in="path",
     *         name="price",
     *         required=true,
     *         @OA\Schema(type="integer"),
     *         @OA\Examples(example="int", value="1", summary="An int value."),
     *     ),
     *     @OA\Response(
     *         response="201",
     *         description="ok",
     *         content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "id":"1",
     *                          "source_city_id":"esf",
     *                          "source_terminal_id":"5",
     *                          "destination_city_id":"teh",
     *                          "destination_terminal_id":"3",
     *                          "moving_day_number":0,
     *                          "moving_time_seconds":28800,
     *                          "traveling_time":240,
     *                          "capacity":26,
     *                          "bus_type":1,
     *                          "price":2000000
     *                     }
     *                 )
     *             )
     *         }
     *     ),
     *   @OA\Response(
     *          response=400,
     *          description="Bad Request",
     *          content={
     *             @OA\MediaType(
     *                 mediaType="application/json",
     *                 @OA\Schema(
     *                     example={
     *                          "status":"HTTP Bad Request",
     *                          "code":"400",
     *                          "data":null
     *                     }
     *                 )
     *             )
     *         }
     *      )
     * )
     */
    public function store(StoreWeeklyScheduleRequest $request): JsonResponse
    {
        if ($request->validated()) {
            $weekly_schedule = WeeklySchedule::create($request->all());
            return response() -> json($weekly_schedule)
                ->setStatusCode(Response::HTTP_CREATED)
                ->header('Content-Type', 'application/json');
        }else{
            return response()->json(['status' => Status::HTTP_BAD_REQUEST , "code" => StatusCode::Failed, "data"=> null])
                ->setStatusCode(Response::HTTP_BAD_REQUEST)
                ->header('Content-Type', 'application/json');
        }
    }
}


